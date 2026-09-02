"""Shared utilities used by multiple modules."""

import logging
import os
import subprocess
import sys
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


def ffmpeg_exe() -> str:
    """Return path to the ffmpeg binary bundled via imageio-ffmpeg."""
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def subprocess_kwargs() -> dict:
    """Extra kwargs to hide the console window on Windows."""
    kw: dict = {}
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kw["startupinfo"] = si
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kw


def fmt_time(ms: float) -> str:
    """Format milliseconds as m:ss."""
    s = int(ms / 1000)
    m = s // 60
    return f"{m}:{s % 60:02d}"


def append_video(
    existing_path: str,
    additional_path: str,
    width: int,
    height: int,
    fps: float,
    timeout: int = 3600,
) -> str:
    """Append one capture to another and atomically replace the first file."""
    if not os.path.isfile(existing_path):
        raise FileNotFoundError(existing_path)
    if not os.path.isfile(additional_path):
        raise FileNotFoundError(additional_path)
    if width <= 0 or height <= 0 or fps <= 0:
        raise ValueError("Video dimensions and FPS must be positive")

    output_path = existing_path + ".append.mp4"
    filter_graph = (
        f"[0:v]fps={fps:.4f},scale={width}:{height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
        "format=yuv420p,setpts=PTS-STARTPTS[first];"
        f"[1:v]fps={fps:.4f},scale={width}:{height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
        "format=yuv420p,setpts=PTS-STARTPTS[second];"
        "[first][second]concat=n=2:v=1:a=0[out]"
    )
    cmd = [
        ffmpeg_exe(), "-y",
        "-i", existing_path,
        "-i", additional_path,
        "-filter_complex", filter_graph,
        "-map", "[out]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            **subprocess_kwargs(),
        )
        if result.returncode != 0 or not os.path.isfile(output_path):
            stderr = result.stderr.decode(errors="replace")[:500] if result.stderr else ""
            raise RuntimeError(f"Could not append capture: {stderr}")
        os.replace(output_path, existing_path)
    finally:
        if os.path.isfile(output_path):
            os.remove(output_path)
    return existing_path


# ── Hardware-accelerated encoder support ────────────────────────────

# Encoder ID → (display name, ffmpeg codec name, quality args)
# Quality args approximate CRF 18 equivalent for each encoder.
ENCODER_PROFILES: Dict[str, Tuple[str, str, List[str]]] = {
    "h264_nvenc":  ("NVIDIA NVENC",    "h264_nvenc",  ["-preset", "p4", "-cq", "18", "-b:v", "0"]),
    "h264_qsv":    ("Intel QuickSync",  "h264_qsv",   ["-preset", "medium", "-global_quality", "18"]),
    "h264_amf":    ("AMD AMF",          "h264_amf",    ["-quality", "quality", "-qp_i", "18", "-qp_p", "18"]),
    "h264_mf":     ("Media Foundation", "h264_mf",     ["-rate_control", "quality", "-quality", "80"]),
    "libx264":     ("Software (x264)",  "libx264",     ["-preset", "medium", "-crf", "18"]),
}

# Order of preference for auto-detection.
# h264_mf (Media Foundation) is excluded: its quality is far below libx264
# and it cannot match CRF-18-equivalent output.  libx264 is the preferred
# software fallback and is always appended last by detect_available_encoders().
_HW_ENCODER_ORDER = ["h264_nvenc", "h264_qsv", "h264_amf"]

# Cached result so we only probe once per process
_available_encoders: List[str] | None = None


def detect_available_encoders() -> List[str]:
    """Probe ffmpeg for available H.264 encoders.

    Returns a list of encoder IDs (e.g. ``["h264_nvenc", "libx264"]``)
    in preference order.  The software fallback ``libx264`` is always
    included last.  Results are cached after the first call.

    Detection algorithm:
    1. Execute ``ffmpeg -encoders`` once.
    2. Parse stdout text for known hardware encoder IDs in preferred order
       (NVENC -> QuickSync -> AMF).
    3. Append software fallback ``libx264`` unconditionally.

    Notes:
    - This is a capability probe, not a guaranteed successful encode probe;
      runtime export still has a fallback chain for launch/mid-stream errors.
    - Caching avoids repeated subprocess overhead on every export.
    """
    global _available_encoders
    if _available_encoders is not None:
        return _available_encoders

    available: List[str] = []
    try:
        ffmpeg = ffmpeg_exe()
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True, timeout=10,
            **subprocess_kwargs(),
        )
        output = result.stdout.decode(errors="replace")
        for enc_id in _HW_ENCODER_ORDER:
            if enc_id in output:
                available.append(enc_id)
    except Exception as exc:
        logger.warning("Encoder probe failed: %s", exc)

    # Software encoder is always available
    available.append("libx264")
    _available_encoders = available
    return available


def best_hw_encoder() -> str:
    """Return the best available encoder ID, preferring HW acceleration.

    Falls back to ``"libx264"`` if no HW encoder is found.

    Selection policy is deterministic and follows ``_HW_ENCODER_ORDER`` so
    UI defaults and exporter behavior are consistent across launches.
    """
    encoders = detect_available_encoders()
    return encoders[0] if encoders else "libx264"


def encoder_display_name(enc_id: str) -> str:
    """Human-readable name for an encoder ID."""
    profile = ENCODER_PROFILES.get(enc_id)
    return profile[0] if profile else enc_id


def build_encoder_args(enc_id: str) -> List[str]:
    """Return ffmpeg arguments for the given encoder ID.

    Returns ``["-c:v", "<codec>", ...quality_args..., "-pix_fmt", "yuv420p"]``.

    Argument construction rules:
    - Unknown IDs fall back to ``libx264`` profile.
    - Profile quality args target roughly CRF-18-equivalent quality per codec.
    - ``yuv420p`` is always appended for broad player compatibility.
    """
    profile = ENCODER_PROFILES.get(enc_id)
    if profile is None:
        profile = ENCODER_PROFILES["libx264"]
    _, codec, quality_args = profile
    args = ["-c:v", codec] + quality_args + ["-pix_fmt", "yuv420p"]
    # Place moov atom at the start so players can open the file
    # immediately without seeking to the end first.
    args += ["-movflags", "+faststart"]
    return args


# ── GIF export support ───────────────────────────────────────────────

# Default frames per second for GIF output (balances quality and file size)
GIF_FPS: int = 15


def build_gif_args(gif_fps: int = GIF_FPS) -> List[str]:
    """Return ffmpeg ``-vf`` filter arguments for high-quality GIF output.

    Uses palette generation (``palettegen`` + ``paletteuse``) for accurate
    colours and bayer dithering to reduce banding artefacts. The graph is
    applied in one ffmpeg pass via ``split``:

    ``fps -> split -> palettegen + paletteuse``

    This avoids temporary files and keeps GIF encoding deterministic.

    Returns ``["-vf", "<filtergraph>", "-loop", "0"]``.
    """
    vf = (
        f"fps={gif_fps},"
        "split[s0][s1];"
        "[s0]palettegen=max_colors=256:stats_mode=diff[p];"
        "[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    return ["-vf", vf, "-loop", "0"]
