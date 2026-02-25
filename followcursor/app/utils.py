"""Shared utilities used by multiple modules."""

import logging
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


# ── Hardware-accelerated encoder support ────────────────────────────

# Encoder ID → (display name, ffmpeg codec name, quality args)
# Quality args approximate CRF 18 equivalent for each encoder.
ENCODER_PROFILES: Dict[str, Tuple[str, str, List[str]]] = {
    "h264_nvenc":  ("NVIDIA NVENC",   "h264_nvenc",  ["-preset", "p4", "-cq", "18", "-b:v", "0"]),
    "h264_qsv":    ("Intel QuickSync", "h264_qsv",   ["-preset", "medium", "-global_quality", "18"]),
    "h264_amf":    ("AMD AMF",         "h264_amf",    ["-quality", "quality", "-qp_i", "18", "-qp_p", "18"]),
    "libx264":     ("Software (x264)", "libx264",     ["-preset", "medium", "-crf", "18"]),
}

# Order of preference for auto-detection
_HW_ENCODER_ORDER = ["h264_nvenc", "h264_qsv", "h264_amf"]

# Cached result so we only probe once per process
_available_encoders: List[str] | None = None


def detect_available_encoders() -> List[str]:
    """Probe ffmpeg for available H.264 encoders.

    Returns a list of encoder IDs (e.g. ``["h264_nvenc", "libx264"]``)
    in preference order.  The software fallback ``libx264`` is always
    included last.  Results are cached after the first call.
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
    """
    profile = ENCODER_PROFILES.get(enc_id)
    if profile is None:
        profile = ENCODER_PROFILES["libx264"]
    _, codec, quality_args = profile
    args = ["-c:v", codec] + quality_args + ["-pix_fmt", "yuv420p"]
    return args
