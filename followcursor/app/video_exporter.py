"""Export pipeline for rendering FollowCursor sessions to MP4/GIF.

Algorithm overview
==================

1. Read source video frames from OpenCV (recorded AVI).
2. Build a *source timeline* from per-frame timestamps when available
    (variable-rate WGC capture), otherwise derive timestamps from source FPS.
3. Build a *constant-FPS output timeline* used by ffmpeg output.
4. For each output timestamp:
    - pick the source frame active at that time (binary search in timestamps),
    - compute zoom/pan from :class:`ZoomEngine`,
    - draw cursor/click overlays at the same timestamp,
    - composite frame + bezel/background with NumPy/OpenCV,
    - enqueue raw BGR bytes for the writer thread.
5. Writer thread drains a bounded queue into ffmpeg stdin.
6. ffmpeg encodes MP4 (hardware encoder with fallback chain) or GIF.

The key design goal is timeline determinism: exported visuals, click effects,
zoom transitions, and optional voiceover audio are all evaluated on the same
timeline so playback stays synchronized.
"""

import logging
import os
import queue
import subprocess
import threading
import time
import bisect
from dataclasses import dataclass

logger = logging.getLogger(__name__)
from typing import List, Optional

import cv2
import numpy as np

from PySide6.QtCore import QObject, Signal

from .models import ZoomKeyframe, MousePosition, ClickEvent, VideoSegment, VoiceoverSegment, ClickEffectPreset, DEFAULT_CLICK_EFFECT
from .zoom_engine import ZoomEngine
from .cursor_renderer import draw_cursor_cv, draw_clicks_cv, _build_cursor_template
from .keystroke_renderer import draw_keystrokes_cv
from .annotation_renderer import render_annotations_cv
from .backgrounds import BackgroundPreset, DEFAULT_PRESET, WAVE_LAYERS
from .frames import FramePreset, DEFAULT_FRAME


from .utils import ffmpeg_exe as _ffmpeg_exe, subprocess_kwargs as _subprocess_kwargs, build_encoder_args as _build_encoder_args, build_gif_args as _build_gif_args


# ── Phase result dataclasses ───────────────────────────────────────

@dataclass
class VideoProbeResult:
    """Results from probing source video metadata."""
    src_fps: float
    total_frames: int
    src_w: int
    src_h: int
    out_w: int
    out_h: int
    fps: float
    is_gif: bool


@dataclass
class GeometryResult:
    """Results from computing device/frame layout geometry."""
    scr_x: int
    scr_y: int
    scr_w: int
    scr_h: int
    base_canvas: np.ndarray
    screen_mask: np.ndarray
    device_mask_u8: Optional[np.ndarray]
    bg: np.ndarray


# ── Numpy-based compositor for export (fast) ────────────────────────

# Device geometry
_BEZEL_REF_W   = 900.0

# Background gradient colors (BGR for OpenCV) — defaults, overridden by preset
_BG_TOP    = np.array([25, 13, 14], dtype=np.uint8)     # #0e0d19
_BG_BOTTOM = np.array([48, 19, 22], dtype=np.uint8)     # #161330


def _preset_to_bgr(preset: BackgroundPreset) -> tuple:
    """Convert a BackgroundPreset to BGR numpy arrays (top, bottom)."""
    r1, g1, b1 = preset.color_top
    r2, g2, b2 = preset.color_bottom
    return (
        np.array([b1, g1, r1], dtype=np.uint8),
        np.array([b2, g2, r2], dtype=np.uint8),
    )
_BEZEL_BGR = np.array([26, 26, 26], dtype=np.uint8)     # #1a1a1a
_EDGE_BGR  = np.array([107, 107, 107], dtype=np.uint8)  # #6b6b6b


def _build_background(w: int, h: int,
                       bg_top: np.ndarray | None = None,
                       bg_bottom: np.ndarray | None = None,
                       kind: str = "solid") -> np.ndarray:
    """Create a background image for the given pattern *kind*.

    Supported kinds: solid, gradient, wavy, radial, spotlight.
    """
    import math

    top = bg_top if bg_top is not None else _BG_TOP
    bot = bg_bottom if bg_bottom is not None else _BG_BOTTOM
    top_f = top.astype(np.float32)
    bot_f = bot.astype(np.float32)

    # Base vertical gradient (used by most patterns as a starting point)
    t = np.linspace(0, 1, h, dtype=np.float32).reshape(h, 1, 1)
    bg = ((1 - t) * top_f + t * bot_f)
    bg = np.broadcast_to(bg, (h, w, 3)).copy()

    if kind == "wavy":
        x_norm = np.linspace(0, 1, w, dtype=np.float32)
        y_idx = np.arange(h, dtype=np.float32).reshape(h, 1)
        for y_frac, amp_frac, freq, phase, alpha, use_top in WAVE_LAYERS:
            wave_color = top_f if use_top else bot_f
            wave_y = (y_frac + amp_frac * np.sin(
                2 * np.pi * freq * x_norm + phase)) * h
            mask = (y_idx >= wave_y.reshape(1, w)).astype(np.float32) * alpha
            mask_3d = mask[:, :, np.newaxis]
            bg = bg * (1 - mask_3d) + wave_color * mask_3d

    elif kind == "radial":
        # Dark fill with radial glow from centre
        bg[:] = bot_f
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2.0, h / 2.0
        radius = max(w, h) * 0.6
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        glow = np.clip(1.0 - dist / radius, 0, 1)[:, :, np.newaxis]
        bg = bg * (1 - glow) + top_f * glow

    elif kind == "spotlight":
        # Dark fill with off-centre glow from upper-right area
        bg[:] = bot_f
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w * 0.8, h * 0.2
        radius = max(w, h) * 0.75
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        glow = np.clip(1.0 - dist / radius, 0, 1)[:, :, np.newaxis]
        bg = bg * (1 - glow) + top_f * glow

    # solid and gradient use the base vertical gradient as-is
    return bg.astype(np.uint8)


def _rounded_rect_contour(x: int, y: int, w: int, h: int, r: int) -> np.ndarray:
    """Return contour points for a rounded rectangle."""
    r = min(r, w // 2, h // 2)
    pts = []
    # Generate arc points for each corner (16 segments per corner)
    for cx, cy, a_start in [
        (x + r, y + r, 180),           # top-left
        (x + w - r, y + r, 270),       # top-right
        (x + w - r, y + h - r, 0),     # bottom-right
        (x + r, y + h - r, 90),        # bottom-left
    ]:
        for j in range(17):
            angle = np.radians(a_start + j * 90 / 16)
            pts.append([int(cx + r * np.cos(angle)), int(cy + r * np.sin(angle))])
    return np.array(pts, dtype=np.int32)


def _build_bezel_mask(canvas_h: int, canvas_w: int,
                      dev_x: int, dev_y: int, dev_w: int, dev_h: int,
                      scr_x: int, scr_y: int, scr_w: int, scr_h: int,
                      outer_r: int, inner_r: int) -> tuple:
    """Pre-build masks for the device bezel (called once per export).

    Returns (device_mask, screen_mask) as uint8 arrays.
    device_mask has 255 where the device body is (rounded rect).
    screen_mask has 255 where the screen opening is (also rounded).
    """
    device_mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    outer_pts = _rounded_rect_contour(dev_x, dev_y, dev_w, dev_h, outer_r)
    cv2.fillPoly(device_mask, [outer_pts], 255)

    screen_mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
    inner_pts = _rounded_rect_contour(scr_x, scr_y, scr_w, scr_h, inner_r)
    cv2.fillPoly(screen_mask, [inner_pts], 255)

    return device_mask, screen_mask, outer_pts, inner_pts


def _build_bezel_layer(canvas_h: int, canvas_w: int,
                       bg: np.ndarray,
                       dev_x: int, dev_y: int, dev_w: int, dev_h: int,
                       scr_x: int, scr_y: int, scr_w: int, scr_h: int,
                       outer_r: int, inner_r: int, edge_thickness: int) -> tuple:
    """Pre-render the static bezel layer once (bg + rounded device + edge).

    Returns (base_canvas, screen_mask) where base_canvas can be copied each
    frame and just the screen area filled with video content.
    """
    device_mask, screen_mask, outer_pts, inner_pts = _build_bezel_mask(
        canvas_h, canvas_w,
        dev_x, dev_y, dev_w, dev_h,
        scr_x, scr_y, scr_w, scr_h,
        outer_r, inner_r,
    )

    base = bg.copy()

    # Drop shadow (4 layers)
    for i in range(4):
        off = 2 + i * 2
        shadow_mask = np.zeros((canvas_h, canvas_w), dtype=np.uint8)
        s_pts = _rounded_rect_contour(
            dev_x + int(off * 0.3), dev_y + off, dev_w, dev_h, outer_r + 2
        )
        cv2.fillPoly(shadow_mask, [s_pts], 255)
        alpha = max(40 - i * 10, 5) / 255.0
        shadow_region = shadow_mask > 0
        base[shadow_region] = (base[shadow_region].astype(np.float32) * (1 - alpha)).astype(np.uint8)

    # Device body (bezel color where device_mask is set, minus screen opening)
    bezel_only = (device_mask > 0) & (screen_mask == 0)
    base[bezel_only] = _BEZEL_BGR

    # Silver edge outline
    cv2.polylines(base, [outer_pts], True, _EDGE_BGR.tolist(), edge_thickness, cv2.LINE_AA)

    # Screen area = black by default
    base[screen_mask > 0] = 0

    return base, screen_mask, inner_pts


def _compose_cv(frame_bgr: np.ndarray, zoom: float, pan_x: float,
                pan_y: float, out_w: int, out_h: int,
                base_canvas: np.ndarray, screen_mask: np.ndarray,
                scr_x: int, scr_y: int, scr_w: int, scr_h: int,
                zoom_video_only: bool = False,
                bg_canvas: np.ndarray | None = None,
                device_mask_u8: np.ndarray | None = None,
                _buf_canvas: np.ndarray | None = None,
                _buf_result: np.ndarray | None = None) -> np.ndarray:
    """Fast compositor — copies pre-rendered bezel, places video in screen,
    then applies zoom.

    *zoom_video_only*=True  (No Frame): crops the source video only;
    background stays static.
    *zoom_video_only*=False (device frame): zooms the device (bezel +
    video) while the background stays static.  Requires *bg_canvas*
    (the background-only layer without bezel).
    *device_mask_u8* — pre-computed mask (255 where bezel differs from
    background).  When ``None``, computed on the fly (slower).
    *_buf_canvas* / *_buf_result* — optional pre-allocated buffers
    (same shape as base_canvas / bg_canvas) to avoid per-frame copies.
    """
    # Reuse pre-allocated buffer instead of copying per-frame
    if _buf_canvas is not None and _buf_canvas.shape == base_canvas.shape:
        np.copyto(_buf_canvas, base_canvas)
        canvas = _buf_canvas
    else:
        canvas = base_canvas.copy()
    fh, fw = frame_bgr.shape[:2]

    if scr_w <= 0 or scr_h <= 0:
        return canvas

    if zoom_video_only and zoom > 1.001:
        # No Frame mode: crop source video, background stays fixed
        # Use warpAffine for sub-pixel precision (avoids jitter from
        # integer pixel snapping during pan/zoom transitions).
        crop_w = fw / zoom
        crop_h = fh / zoom
        cx = pan_x * fw - crop_w / 2
        cy = pan_y * fh - crop_h / 2
        cx = max(0.0, min(cx, fw - crop_w))
        cy = max(0.0, min(cy, fh - crop_h))
        # Inverse affine: maps each output pixel (dx, dy) → source pixel
        #   src_x = (crop_w / scr_w) * dx + cx
        #   src_y = (crop_h / scr_h) * dy + cy
        M = np.float32([
            [crop_w / scr_w, 0, cx],
            [0, crop_h / scr_h, cy],
        ])
        resized = cv2.warpAffine(
            frame_bgr, M, (scr_w, scr_h),
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        )
        roi_mask = screen_mask[scr_y:scr_y + scr_h, scr_x:scr_x + scr_w]
        roi = canvas[scr_y:scr_y + scr_h, scr_x:scr_x + scr_w]
        np.copyto(roi, resized, where=roi_mask[:, :, np.newaxis] > 0)
        return canvas

    # Place video into the bezel canvas at 1×
    resized = cv2.resize(frame_bgr, (scr_w, scr_h),
                         interpolation=cv2.INTER_AREA)
    roi_mask = screen_mask[scr_y:scr_y + scr_h, scr_x:scr_x + scr_w]
    roi = canvas[scr_y:scr_y + scr_h, scr_x:scr_x + scr_w]
    np.copyto(roi, resized, where=roi_mask[:, :, np.newaxis] > 0)

    # Device frame + zoom: move the device closer, background stays static
    if not zoom_video_only and zoom > 1.001 and bg_canvas is not None:
        H, W = canvas.shape[:2]
        # Focus point in canvas coords
        fx = scr_x + pan_x * scr_w
        fy = scr_y + pan_y * scr_h

        # Use warpAffine for sub-pixel precision — a single resample step
        # maps output pixels directly to floating-point canvas coords,
        # eliminating the integer pixel snapping that caused frame jitter.
        #
        # For output pixel (dx, dy), the canvas source pixel is:
        #   src_x = dx / zoom + (fx - W / (2 * zoom))
        #   src_y = dy / zoom + (fy - H / (2 * zoom))
        half_vw = W / (2.0 * zoom)
        half_vh = H / (2.0 * zoom)
        # Clamp focus so viewport stays within canvas bounds
        fx_c = max(half_vw, min(fx, W - half_vw))
        fy_c = max(half_vh, min(fy, H - half_vh))

        M = np.float32([
            [1.0 / zoom, 0, fx_c - half_vw],
            [0, 1.0 / zoom, fy_c - half_vh],
        ])
        cropped_device = cv2.warpAffine(
            canvas, M, (W, H),
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        )

        # Composite: static background + zoomed device on top
        if _buf_result is not None and bg_canvas is not None and _buf_result.shape == bg_canvas.shape:
            np.copyto(_buf_result, bg_canvas)
            result = _buf_result
        else:
            result = bg_canvas.copy()
        if device_mask_u8 is None:
            device_mask_u8 = (np.any(base_canvas != bg_canvas, axis=2)
                              .astype(np.uint8) * 255)
        cropped_mask = cv2.warpAffine(
            device_mask_u8, M, (W, H),
            flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP,
        )
        mask_bool = cropped_mask > 127
        np.copyto(result, cropped_device, where=mask_bool[:, :, np.newaxis])
        return result

    return canvas


def _merge_voiceover_segments(
    segments: list,
    duration_ms: float,
    trim_start_ms: float,
    trim_end_ms: float,
    ffmpeg: str,
) -> str:
    """Merge voiceover clips into one WAV aligned to export timeline.

    Each voiceover clip is timestamped in recording time. The merge step uses
    ffmpeg audio filters so export can mux a single audio input:

    - ``adelay`` offsets each clip to its timeline position.
    - ``amix`` combines all delayed clips into one stream.

    For trimmed exports, timestamps are shifted by ``trim_start_ms`` so
    voiceover timing remains correct in the trimmed output.

    Returns the merged WAV path, or ``""`` when merge fails.
    """
    import tempfile
    if not segments:
        return ""

    # Compute effective trim offset — voiceover timestamps are relative
    # to the full recording, so we shift them by trim_start_ms.
    offset_ms = trim_start_ms if trim_start_ms > 0 else 0.0

    output_path = os.path.join(
        tempfile.gettempdir(),
        f"followcursor_vo_merged_{os.getpid()}_{int(time.time())}.wav",
    )

    if len(segments) == 1:
        seg = segments[0]
        delay = max(0, int(seg.timestamp - offset_ms))
        # Single segment: just delay it
        cmd = [
            ffmpeg, "-y",
            "-i", seg.audio_path,
            "-af", f"adelay={delay}|{delay}",
            "-ar", "44100",
            output_path,
        ]
    else:
        # Multiple segments: build a complex filtergraph
        inputs: list[str] = []
        filter_parts: list[str] = []
        for i, seg in enumerate(segments):
            inputs += ["-i", seg.audio_path]
            delay = max(0, int(seg.timestamp - offset_ms))
            filter_parts.append(f"[{i}]adelay={delay}|{delay}[a{i}]")

        mix_inputs = "".join(f"[a{i}]" for i in range(len(segments)))
        filter_parts.append(
            f"{mix_inputs}amix=inputs={len(segments)}:duration=longest:normalize=0"
        )
        filtergraph = ";".join(filter_parts)

        cmd = [ffmpeg, "-y"] + inputs + [
            "-filter_complex", filtergraph,
            "-ar", "44100",
            output_path,
        ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=120,
            **_subprocess_kwargs(),
        )
        if result.returncode == 0 and os.path.isfile(output_path):
            logger.info("Merged %d voiceover segments into %s", len(segments), output_path)
            return output_path
        stderr = result.stderr.decode(errors="replace")[:300] if result.stderr else ""
        logger.warning("Voiceover merge failed (rc=%d): %s", result.returncode, stderr)
    except Exception as exc:
        logger.warning("Voiceover merge error: %s", exc)
    return ""


class GeometryComputer:
    """Computes device/frame layout geometry for video export.
    
    Pure-logic class with no Qt or OpenCV dependencies in the constructor,
    making it easily testable. All geometry calculations are deterministic
    given the input parameters.
    """
    
    def __init__(
        self,
        canvas_w: int,
        canvas_h: int,
        src_w: int,
        src_h: int,
        frame_preset: FramePreset,
    ):
        """Initialize geometry computer with canvas and source dimensions.
        
        Args:
            canvas_w: Output canvas width in pixels
            canvas_h: Output canvas height in pixels
            src_w: Source video width in pixels
            src_h: Source video height in pixels
            frame_preset: Frame preset defining bezel/padding parameters
        """
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h
        self.src_w = src_w
        self.src_h = src_h
        self.frame_preset = frame_preset
        self.video_aspect = src_w / max(src_h, 1)
    
    def compute(self) -> dict:
        """Compute all geometry parameters for the given configuration.
        
        Returns:
            Dictionary with keys:
                - scr_x, scr_y: screen position in canvas
                - scr_w, scr_h: screen dimensions
                - dev_x, dev_y: device position (if frame present)
                - dev_w, dev_h: device dimensions (if frame present)
                - outer_r, inner_r: corner radii (if frame present)
                - edge_thickness: edge line thickness (if frame present)
                - bw: bezel width (if frame present)
        """
        fp = self.frame_preset
        W, H = float(self.canvas_w), float(self.canvas_h)
        
        if fp.is_none:
            # No frame — video fills full canvas
            if W / H > self.video_aspect:
                scr_h = self.canvas_h
                scr_w = int(H * self.video_aspect)
            else:
                scr_w = self.canvas_w
                scr_h = int(W / self.video_aspect)
            scr_x = (self.canvas_w - scr_w) // 2
            scr_y = (self.canvas_h - scr_h) // 2
            
            return {
                "scr_x": scr_x,
                "scr_y": scr_y,
                "scr_w": scr_w,
                "scr_h": scr_h,
            }
        
        # Device frame present — compute bezel geometry
        pad_x = W * fp.padding
        pad_y = H * fp.padding
        avail_w = W - 2 * pad_x
        avail_h = H - 2 * pad_y
        
        preliminary_scale = avail_w / _BEZEL_REF_W
        bw_est = fp.bezel_width * preliminary_scale
        
        dev_h = avail_h
        scr_h_try = dev_h - 2 * bw_est
        scr_w_try = scr_h_try * self.video_aspect
        dev_w = scr_w_try + 2 * bw_est
        if dev_w > avail_w:
            dev_w = avail_w
            scr_w_try = dev_w - 2 * bw_est
            scr_h_try = scr_w_try / self.video_aspect
            dev_h = scr_h_try + 2 * bw_est
        
        dev_x_i = int((W - dev_w) / 2)
        dev_y_i = int((H - dev_h) / 2)
        dev_w_i = int(dev_w)
        dev_h_i = int(dev_h)
        
        scale = dev_w / _BEZEL_REF_W
        bw = int(fp.bezel_width * scale)
        outer_r = int(fp.outer_radius * scale)
        inner_r = max(int(fp.inner_radius * scale), 2) if fp.inner_radius > 0 else 0
        edge_thickness = max(1, int(fp.edge_width * scale))
        
        scr_x = dev_x_i + bw
        scr_y = dev_y_i + bw
        scr_w = dev_w_i - 2 * bw
        scr_h = dev_h_i - 2 * bw
        
        return {
            "scr_x": scr_x,
            "scr_y": scr_y,
            "scr_w": scr_w,
            "scr_h": scr_h,
            "dev_x": dev_x_i,
            "dev_y": dev_y_i,
            "dev_w": dev_w_i,
            "dev_h": dev_h_i,
            "outer_r": outer_r,
            "inner_r": inner_r,
            "edge_thickness": edge_thickness,
            "bw": bw,
        }


class VideoExporter(QObject):
    """Reads the raw recording, applies zoom/pan per-frame, writes H.264 MP4 or GIF."""

    progress = Signal(float)  # 0.0–1.0
    finished = Signal(str)    # output path
    error = Signal(str)
    status = Signal(str)      # status text updates (e.g. encoder fallback)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: Optional[threading.Thread] = None

    # ── public API ──────────────────────────────────────────────────

    def export(
        self,
        input_path: str,
        output_path: str,
        keyframes: List[ZoomKeyframe],
        actual_fps: float = 0.0,
        mouse_track: Optional[List[MousePosition]] = None,
        monitor_rect: Optional[dict] = None,
        bg_preset: Optional[BackgroundPreset] = None,
        frame_preset: Optional[FramePreset] = None,
        click_events: Optional[List[ClickEvent]] = None,
        click_preset: Optional[ClickEffectPreset] = None,
        output_dim=None,
        duration_ms: float = 0.0,
        frame_timestamps: Optional[List[float]] = None,
        trim_start_ms: float = 0.0,
        trim_end_ms: float = 0.0,
        encoder_id: str = "libx264",
        voiceover_segments: Optional[List[VoiceoverSegment]] = None,
        video_segments: Optional[List[VideoSegment]] = None,
        key_events: Optional[List] = None,
        keystroke_config: Optional = None,
        annotations = None,
    ) -> None:
        """Start export in a background thread.

        *output_dim* — (width, height) tuple or ``"auto"`` / ``None``
        to use the source video's native resolution.
        *duration_ms* — wall-clock recording duration for accurate
        progress tracking (``cv2.CAP_PROP_FRAME_COUNT`` is unreliable
        for huffyuv AVI containers).
        *frame_timestamps* — per-frame ms offsets from recording start.
        When provided, gives accurate time mapping for variable-rate
        recordings (e.g. WGC capture).
        *trim_start_ms* / *trim_end_ms* — if non-zero, only export the
        trimmed region of the video.
        *encoder_id* — ffmpeg encoder to use (e.g. ``"h264_nvenc"``,
        ``"h264_qsv"``, ``"h264_amf"``, ``"libx264"``).
        *voiceover_segments* — optional list of ``VoiceoverSegment``
        objects; each with an audio file to mux at a specific time.
        *video_segments* — optional list of ``VideoSegment`` objects;
        when present, only frames within these time ranges are exported.
        *key_events* — optional list of ``KeyEvent`` objects for keystroke rendering.
        *keystroke_config* — optional ``KeystrokeOverlayConfig`` for keystroke overlay settings.
        *annotations* — optional ``AnnotationCollection`` for text, arrow, and highlight annotations.
        """
        self._thread = threading.Thread(
            target=self._run,
            args=(input_path, output_path, keyframes, actual_fps,
                  mouse_track or [], monitor_rect or {},
                  bg_preset or DEFAULT_PRESET,
                  frame_preset or DEFAULT_FRAME,
                  click_events or [],
                  click_preset or DEFAULT_CLICK_EFFECT,
                  output_dim,
                  duration_ms,
                  frame_timestamps,
                  trim_start_ms,
                  trim_end_ms,
                  encoder_id,
                  voiceover_segments or [],
                  video_segments or [],
                  key_events or [],
                  keystroke_config,
                  annotations),
            daemon=True,
        )
        self._thread.start()

    # ── internal ────────────────────────────────────────────────────

    def _probe_video(
        self,
        cap: cv2.VideoCapture,
        actual_fps: float,
        duration_ms: float,
        frame_timestamps: Optional[List[float]],
        output_dim,
        output_path: str,
    ) -> Optional[VideoProbeResult]:
        """Phase 1: Probe source video metadata and determine output parameters.
        
        Returns:
            VideoProbeResult on success, None on error (emits self.error signal).
        """
        src_fps = cap.get(cv2.CAP_PROP_FPS)
        if src_fps <= 0 or src_fps > 120:
            src_fps = 30.0
        if actual_fps > 0:
            src_fps = actual_fps
        cap_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # After the post-recording remux the metadata is correct.
        # For legacy videos, detect metadata/duration mismatch and
        # recount frames if needed.
        meta_dur = (cap_frame_count / src_fps * 1000) if src_fps > 0 else 0
        need_recount = False
        if duration_ms > 0 and meta_dur > 0:
            ratio = meta_dur / duration_ms
            if ratio < 0.90 or ratio > 1.10:
                need_recount = True

        if need_recount:
            real_frame_count = 0
            while cap.grab():
                real_frame_count += 1
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            if duration_ms > 0 and real_frame_count > 0:
                src_fps = real_frame_count / (duration_ms / 1000.0)
            total_frames = real_frame_count if real_frame_count > 0 else cap_frame_count
        else:
            total_frames = cap_frame_count
        if total_frames <= 0 and frame_timestamps:
            total_frames = len(frame_timestamps)
        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if src_w == 0 or src_h == 0:
            self.error.emit("Invalid video dimensions")
            return None

        # Determine output canvas size
        if output_dim and output_dim != "auto" and isinstance(output_dim, (tuple, list)):
            out_w, out_h = int(output_dim[0]), int(output_dim[1])
            # Ensure even dimensions (required by H.264)
            out_w = out_w + (out_w % 2)
            out_h = out_h + (out_h % 2)
        else:
            out_w, out_h = src_w, src_h

        # Ensure even dimensions (H.264 requires even dimensions)
        out_w = out_w + (out_w % 2)
        out_h = out_h + (out_h % 2)

        # Normalise extension: allow .gif; everything else becomes .mp4
        is_gif = output_path.lower().endswith(".gif")

        # Export on a stable CFR timeline.  WGC recordings can have sparse,
        # irregular source frames (only when the image changes).  Keeping
        # a very low averaged FPS here makes output choppy and drifts
        # overlays/audio relative to visual content.  Use at least 24 fps
        # for MP4 (cinematic standard — smooth enough without inflating
        # frame count as much as 30 fps would).
        fps = src_fps
        if not is_gif and fps < 24.0:
            fps = 24.0
        logger.info(
            "Export timing | source_fps=%.2f output_fps=%.2f total_frames=%d frame_timestamps=%d",
            src_fps,
            fps,
            total_frames,
            len(frame_timestamps or []),
        )

        return VideoProbeResult(
            src_fps=src_fps,
            total_frames=total_frames,
            src_w=src_w,
            src_h=src_h,
            out_w=out_w,
            out_h=out_h,
            fps=fps,
            is_gif=is_gif,
        )

    def _compute_geometry(
        self,
        probe: VideoProbeResult,
        bg_preset: BackgroundPreset,
        frame_preset: FramePreset,
    ) -> GeometryResult:
        """Phase 2: Compute device/frame layout and build static layers.
        
        Returns:
            GeometryResult containing screen coordinates, canvas, and masks.
        """
        w, h = probe.out_w, probe.out_h
        
        # Pre-build the gradient background
        self.status.emit("Building background & frame…")
        bg_top_bgr, bg_bottom_bgr = _preset_to_bgr(bg_preset)
        bg = _build_background(w, h, bg_top_bgr, bg_bottom_bgr,
                               kind=bg_preset.kind)

        # Compute device geometry using GeometryComputer
        geom_comp = GeometryComputer(w, h, probe.src_w, probe.src_h, frame_preset)
        geom = geom_comp.compute()
        
        scr_x = geom["scr_x"]
        scr_y = geom["scr_y"]
        scr_w = geom["scr_w"]
        scr_h = geom["scr_h"]
        
        # Build canvas and masks based on frame preset
        if frame_preset.is_none:
            # No frame — simple bg canvas
            base_canvas = bg.copy()
            screen_mask = np.zeros((h, w), dtype=np.uint8)
            screen_mask[scr_y:scr_y + scr_h, scr_x:scr_x + scr_w] = 255
            device_mask_u8 = None
        else:
            bw = geom["bw"]
            if bw > 0:
                # Pre-render the bezel (bg + shadow + bezel + edge)
                base_canvas, screen_mask, _ = _build_bezel_layer(
                    h, w, bg,
                    geom["dev_x"], geom["dev_y"], geom["dev_w"], geom["dev_h"],
                    scr_x, scr_y, scr_w, scr_h,
                    geom["outer_r"], geom["inner_r"], geom["edge_thickness"],
                )
            else:
                # Shadow-only or zero-bezel: just shadow + rounded screen
                base_canvas = bg.copy()
                if frame_preset.shadow_layers > 0 and geom["outer_r"] > 0:
                    for i in range(frame_preset.shadow_layers):
                        off = 2 + i * 2
                        shadow_mask = np.zeros((h, w), dtype=np.uint8)
                        s_pts = _rounded_rect_contour(
                            geom["dev_x"] + int(off * 0.3), geom["dev_y"] + off,
                            geom["dev_w"], geom["dev_h"], geom["outer_r"] + 2
                        )
                        cv2.fillPoly(shadow_mask, [s_pts], 255)
                        alpha = max(40 - i * 10, 5) / 255.0
                        shadow_region = shadow_mask > 0
                        base_canvas[shadow_region] = (
                            base_canvas[shadow_region].astype(np.float32) * (1 - alpha)
                        ).astype(np.uint8)
                screen_mask = np.zeros((h, w), dtype=np.uint8)
                if geom["inner_r"] > 0:
                    inner_pts = _rounded_rect_contour(scr_x, scr_y, scr_w, scr_h, geom["inner_r"])
                    cv2.fillPoly(screen_mask, [inner_pts], 255)
                else:
                    screen_mask[scr_y:scr_y + scr_h, scr_x:scr_x + scr_w] = 255
                base_canvas[screen_mask > 0] = 0
            
            # Pre-compute device region mask for zoom compositing
            device_mask_u8 = (np.any(base_canvas != bg, axis=2)
                              .astype(np.uint8) * 255)
        
        return GeometryResult(
            scr_x=scr_x,
            scr_y=scr_y,
            scr_w=scr_w,
            scr_h=scr_h,
            base_canvas=base_canvas,
            screen_mask=screen_mask,
            device_mask_u8=device_mask_u8,
            bg=bg,
        )

    def _run(
        self,
        input_path: str,
        output_path: str,
        keyframes: List[ZoomKeyframe],
        actual_fps: float,
        mouse_track: List[MousePosition],
        monitor_rect: dict,
        bg_preset: BackgroundPreset,
        frame_preset: FramePreset,
        click_events: List[ClickEvent],
        click_preset: ClickEffectPreset,
        output_dim=None,
        duration_ms: float = 0.0,
        frame_timestamps: Optional[List[float]] = None,
        trim_start_ms: float = 0.0,
        trim_end_ms: float = 0.0,
        encoder_id: str = "libx264",
        voiceover_segments: Optional[List[VoiceoverSegment]] = None,
        video_segments: Optional[List[VideoSegment]] = None,
        key_events: Optional[List] = None,
        keystroke_config = None,
        annotations = None,
    ) -> None:
        """Execute the full export algorithm on a worker thread.

        High-level phases:
        1. Probe source metadata and reconcile FPS/frame-count uncertainty.
        2. Precompute static composition layers (background, bezel masks).
        3. Prepare audio (optional voiceover merge).
        4. Render frames on a deterministic CFR output timeline:
           source timestamp lookup -> zoom/cursor/click -> compose -> queue.
        5. Encode via ffmpeg with hardware fallback chain.

        Error handling strategy:
        - Recover from unsupported HW encoders by retrying others.
        - Catch pipe errors from ffmpeg stdin writes.
        - Emit user-facing signal messages instead of raising to UI thread.
        """
        proc: subprocess.Popen | None = None
        cap: cv2.VideoCapture | None = None
        _merged_audio_path: str = ""
        try:
            self.status.emit("Preparing video…")
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                self.error.emit(f"Cannot open {input_path}")
                return

            # Phase 1: Probe video metadata
            probe = self._probe_video(
                cap, actual_fps, duration_ms, frame_timestamps,
                output_dim, output_path
            )
            if probe is None:
                return  # Error already emitted

            w, h = probe.out_w, probe.out_h
            src_fps = probe.src_fps
            total_frames = probe.total_frames
            fps = probe.fps
            _is_gif = probe.is_gif
            
            # Update output_path extension if needed
            if not _is_gif and not output_path.lower().endswith(".mp4"):
                output_path = output_path.rsplit(".", 1)[0] + ".mp4"

            # Phase 2: Compute geometry and build static layers
            geom = self._compute_geometry(probe, bg_preset, frame_preset)
            scr_x, scr_y, scr_w, scr_h = geom.scr_x, geom.scr_y, geom.scr_w, geom.scr_h
            base_canvas = geom.base_canvas
            screen_mask = geom.screen_mask
            _device_mask_u8 = geom.device_mask_u8
            bg = geom.bg

            if w < 2 or h < 2:
                self.error.emit("Output dimensions too small for encoding")
                return

            # Pipe raw BGR frames to ffmpeg for encoding (H.264 or GIF)
            ffmpeg = _ffmpeg_exe()
            original_encoder_id = encoder_id

            # Build merged audio from voiceover segments (if any)
            _has_audio = False
            if voiceover_segments and not _is_gif:
                ready = [s for s in voiceover_segments if s.audio_path and os.path.isfile(s.audio_path)]
                if ready:
                    self.status.emit(f"Merging {len(ready)} voiceover segment(s)\u2026")
                    _merged_audio_path = _merge_voiceover_segments(
                        ready, duration_ms, trim_start_ms, trim_end_ms, ffmpeg
                    )
                    _has_audio = bool(_merged_audio_path) and os.path.isfile(_merged_audio_path)
                    if _has_audio:
                        logger.info("Voiceover audio ready: %s", _merged_audio_path)
                    else:
                        logger.warning("Voiceover merge produced no output, exporting without audio")

            def _launch_ffmpeg(enc_id: str) -> subprocess.Popen:
                """Start ffmpeg process configured for current export mode.

                MP4 mode:
                - receives raw BGR frames on stdin,
                - encodes using selected H.264 encoder args,
                - optionally muxes merged voiceover WAV.

                GIF mode:
                - receives raw BGR frames on stdin,
                - applies palettegen/paletteuse filtergraph.
                """
                if _is_gif:
                    gif_args = _build_gif_args()
                    cmd = [
                        ffmpeg, "-y",
                        "-f", "rawvideo",
                        "-vcodec", "rawvideo",
                        "-s", f"{w}x{h}",
                        "-pix_fmt", "bgr24",
                        "-r", str(fps),
                        "-i", "pipe:",
                    ] + gif_args + [
                        output_path,
                    ]
                    logger.info("Launching ffmpeg for GIF export: %s", " ".join(cmd))
                else:
                    enc_args = _build_encoder_args(enc_id)
                    cmd = [
                        ffmpeg, "-y",
                        "-f", "rawvideo",
                        "-vcodec", "rawvideo",
                        "-s", f"{w}x{h}",
                        "-pix_fmt", "bgr24",
                        "-r", str(fps),
                        "-i", "pipe:",
                    ]
                    # Add merged audio input if available
                    if _has_audio:
                        cmd += ["-i", _merged_audio_path]
                    cmd += enc_args
                    if _has_audio:
                        cmd += ["-c:a", "aac", "-b:a", "192k"]
                    cmd += [output_path]
                    logger.info("Launching ffmpeg with encoder %s: %s", enc_id, " ".join(cmd))
                return subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    **_subprocess_kwargs(),
                )

            def _encode_frames(proc: subprocess.Popen) -> bool:
                """Render and feed frames to ffmpeg using producer/consumer flow.

                Timeline algorithm
                ------------------
                - Build ``source_timestamps`` from recorded frame timestamps.
                - Iterate output timeline in fixed steps: ``t = start + n/fps``.
                - For each output time ``t``:
                    - binary-search source frame index active at ``t``,
                    - advance OpenCV decoder up to that index,
                    - render overlays/composition evaluated at ``t``.

                Concurrency algorithm
                ---------------------
                - Producer (this thread): compose ndarray -> bytes -> queue.
                - Consumer (writer thread): queue -> ``proc.stdin.write``.

                This overlap prevents encoder starvation and keeps export
                throughput high without sacrificing timeline correctness.
                """
                nonlocal frame_timestamps  # read-only access

                engine = ZoomEngine()
                for kf in keyframes:
                    engine.add_keyframe(kf)

                # Pre-build cursor template for overlay
                # Use scr_h (screen area height) with same factor as preview
                # compositor (screen_rect_h * 0.032) for visual consistency
                cursor_h_px = max(16, int(scr_h * 0.032))
                c_bgr, c_alpha = _build_cursor_template(cursor_h_px)
                m_left = monitor_rect.get("left", 0)
                m_top = monitor_rect.get("top", 0)
                m_w = max(monitor_rect.get("width", w), 1)
                m_h = max(monitor_rect.get("height", h), 1)
                _has_cursor = len(mouse_track) > 0 and m_w > 0
                _has_clicks = len(click_events) > 0 and m_w > 0

                # Build source-frame timestamps used to map output timeline
                # time -> source frame index.  This mirrors preview playback,
                # which also picks frames from per-frame timestamps.
                if frame_timestamps:
                    source_timestamps = []
                    last_ts = 0.0
                    for t in frame_timestamps[:total_frames]:
                        ts = float(t)
                        if ts < last_ts:
                            ts = last_ts
                        source_timestamps.append(ts)
                        last_ts = ts
                else:
                    source_timestamps = [
                        (i / src_fps) * 1000.0 for i in range(total_frames)
                    ]
                if not source_timestamps:
                    return False

                # ── Pipeline: compositor → queue → writer thread → ffmpeg ──
                _QUEUE_DEPTH = 16
                frame_q: queue.Queue = queue.Queue(maxsize=_QUEUE_DEPTH)
                pipe_err = threading.Event()

                def _pipe_writer() -> None:
                    """Drain frame queue into ffmpeg's stdin pipe."""
                    while True:
                        data = frame_q.get()
                        if data is None:
                            break
                        try:
                            proc.stdin.write(data)
                        except (BrokenPipeError, OSError, ValueError):
                            pipe_err.set()
                            break

                writer_t = threading.Thread(target=_pipe_writer, daemon=True)
                writer_t.start()

                def _enqueue(data: bytes) -> bool:
                    """Put frame data into the queue.  Returns False on pipe error."""
                    while not pipe_err.is_set():
                        try:
                            frame_q.put(data, timeout=0.5)
                            return True
                        except queue.Full:
                            continue
                    return False

                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                exported = 0
                ret, first_frame = cap.read()
                if not ret:
                    frame_q.put(None)
                    writer_t.join(timeout=5)
                    return False
                src_idx = 0
                last_f = first_frame.copy()

                eff_ts = trim_start_ms if trim_start_ms > 0 else 0.0
                if trim_end_ms > 0:
                    eff_te = trim_end_ms
                elif duration_ms > 0:
                    eff_te = duration_ms
                else:
                    eff_te = source_timestamps[-1]
                if eff_te < eff_ts:
                    eff_te = eff_ts

                # Build a sorted list of (start, end) time ranges from video
                # segments.  Only frames whose source timestamp falls inside
                # one of these ranges will be exported (ripple delete).
                _seg_ranges: list[tuple[float, float]] = []
                _seg_starts: list[float] = []  # pre-extracted for bisect
                if video_segments:
                    _seg_ranges = sorted(
                        (s.start_ms, s.end_ms) for s in video_segments
                    )
                    _seg_starts = [s for s, _ in _seg_ranges]

                # Move decoder to the source frame active at trim start.
                start_src_idx = max(0, bisect.bisect_right(source_timestamps, eff_ts) - 1)
                start_src_idx = min(start_src_idx, len(source_timestamps) - 1)
                while src_idx < start_src_idx:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    src_idx += 1
                    last_f = frame.copy()

                t_total = max(1, int(engine.compute_output_duration(
                    duration_ms or eff_te, eff_ts, eff_te,
                ) / 1000.0 * fps) + 1)
                out_idx = 0
                t_ms = eff_ts  # recording-time cursor (advances by speed-adjusted intervals)

                # Pre-allocate reusable frame buffers to avoid per-frame copies
                _buf_canvas = base_canvas.copy()
                _buf_result = bg.copy() if bg is not None else None

                while True:
                    if t_ms > eff_te + 0.0001:
                        break

                    # Skip frames outside any video segment (ripple delete).
                    # Uses half-open intervals [start, end) for interior
                    # segments; the last segment's end is inclusive to
                    # avoid clipping the final frame.
                    # Uses bisect for O(log n) membership check.
                    if _seg_ranges:
                        in_seg = False
                        # Binary search: find the last segment whose start <= t_ms
                        idx = bisect.bisect_right(_seg_starts, t_ms) - 1
                        if idx >= 0:
                            s, e = _seg_ranges[idx]
                            # Last segment uses inclusive end [s, e]; others use [s, e)
                            if idx == len(_seg_ranges) - 1:
                                in_seg = (s <= t_ms <= e)
                            else:
                                in_seg = (s <= t_ms < e)
                        if not in_seg:
                            out_idx += 1
                            continue

                    # Pick the source frame for this output timestamp
                    target_src_idx = max(0, bisect.bisect_right(source_timestamps, t_ms) - 1)
                    target_src_idx = min(target_src_idx, len(source_timestamps) - 1)

                    while src_idx < target_src_idx:
                        ret, frame = cap.read()
                        if not ret:
                            # Keep reusing the last decoded frame if the
                            # container has fewer readable frames than expected.
                            src_idx = target_src_idx
                            break
                        src_idx += 1
                        last_f = frame.copy()

                    frame = last_f.copy()

                    zoom, px, py = engine.compute_at(t_ms)

                    if _has_cursor:
                        draw_cursor_cv(
                            frame, mouse_track, t_ms,
                            m_left, m_top, m_w, m_h,
                            c_bgr, c_alpha,
                        )
                    if _has_clicks:
                        draw_clicks_cv(
                            frame, click_events, t_ms,
                            m_left, m_top, m_w, m_h,
                            click_preset,
                        )
                    
                    # Draw keystroke overlay if enabled
                    if keystroke_config and keystroke_config.enabled and key_events:
                        draw_keystrokes_cv(
                            frame, key_events, t_ms, keystroke_config,
                            m_left, m_top, m_w, m_h,
                        )
                    
                    # Draw annotations if present
                    if annotations:
                        render_annotations_cv(
                            frame, annotations, t_ms, m_w, m_h
                        )

                    composed = _compose_cv(
                        frame, zoom, px, py, w, h,
                        base_canvas, screen_mask,
                        scr_x, scr_y, scr_w, scr_h,
                        zoom_video_only=frame_preset.is_none,
                        bg_canvas=bg,
                        device_mask_u8=_device_mask_u8,
                        _buf_canvas=_buf_canvas,
                        _buf_result=_buf_result,
                    )
                    if not _enqueue(composed.tobytes()):
                        break
                    exported += 1
                    out_idx += 1
                    # Advance recording-time cursor by speed-adjusted interval
                    seg_speed = engine.get_speed_at(t_ms, duration_ms or eff_te)
                    t_ms += (1.0 / fps) * 1000.0 * max(seg_speed, 0.01)

                    if exported % 10 == 0:
                        self.progress.emit(min(1.0, exported / t_total))

                # Extra frames for zoom-out tail
                if last_f is not None and engine.keyframes and not pipe_err.is_set():
                    last_kf = engine.keyframes[-1]
                    end_time = last_kf.timestamp + last_kf.duration
                    # Use output-aligned time for the last exported frame
                    video_end_ms = eff_te
                    if trim_end_ms <= 0 and end_time > video_end_ms:
                        extra = int((end_time - video_end_ms) / 1000.0 * fps) + 1
                        for ei in range(extra):
                            t_ms = video_end_ms + ((ei + 1) / fps) * 1000.0
                            zoom, px, py = engine.compute_at(t_ms)
                            fc = last_f.copy()
                            if _has_cursor:
                                draw_cursor_cv(
                                    fc, mouse_track, t_ms,
                                    m_left, m_top, m_w, m_h,
                                    c_bgr, c_alpha,
                                )
                            if _has_clicks:
                                draw_clicks_cv(
                                    fc, click_events, t_ms,
                                    m_left, m_top, m_w, m_h,
                                    click_preset,
                                )
                            
                            # Draw keystroke overlay if enabled
                            if keystroke_config and keystroke_config.enabled and key_events:
                                draw_keystrokes_cv(
                                    fc, key_events, t_ms, keystroke_config,
                                    m_left, m_top, m_w, m_h,
                                )
                            
                            # Draw annotations if present
                            if annotations:
                                render_annotations_cv(
                                    fc, annotations, t_ms, m_w, m_h
                                )
                            
                            composed = _compose_cv(
                                fc, zoom, px, py, w, h,
                                base_canvas, screen_mask,
                                scr_x, scr_y, scr_w, scr_h,
                                zoom_video_only=frame_preset.is_none,
                                bg_canvas=bg,
                                device_mask_u8=_device_mask_u8,
                                _buf_canvas=_buf_canvas,
                                _buf_result=_buf_result,
                            )
                            if not _enqueue(composed.tobytes()):
                                break

                # Signal writer thread to finish and wait for it
                frame_q.put(None)
                writer_t.join(timeout=30)
                return not pipe_err.is_set()

            # ── Try encoding (with HW fallback chain for MP4; direct for GIF) ──

            if _is_gif:
                # GIF export uses palette-based encoding — no fallback chain
                self.status.emit("Rendering frames for GIF\u2026")
                proc = _launch_ffmpeg(encoder_id)
                pipe_ok = _encode_frames(proc)
                proc.stdin.close()
                self.status.emit("Generating GIF palette\u2026")
                # GIF palettegen buffers all frames before writing; allow more time
                try:
                    stderr_out = proc.communicate(timeout=300)[1]
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stderr_out = proc.communicate()[1]
                stderr_text = stderr_out.decode(errors="replace") if stderr_out else ""
                cap.release()
                if proc.returncode != 0:
                    err_msg = stderr_text.strip()[-800:] if stderr_text else "Unknown ffmpeg error"
                    logger.error("GIF export failed (rc=%s): %s", proc.returncode, err_msg)
                    self.error.emit(f"GIF export error: {err_msg[:500]}")
                    return
                self.progress.emit(1.0)
                self.finished.emit(output_path)
                return

            # ── MP4: try encoding with HW fallback chain ──────────────
            #
            # Build a fallback chain: try other available HW encoders
            # before falling back to software (libx264).
            from .utils import detect_available_encoders, encoder_display_name
            enc_label = encoder_display_name(encoder_id)
            self.status.emit(f"Encoding with {enc_label}…")
            available = detect_available_encoders()
            # Build chain: encoders after the current one in preference order
            _fallback_chain: List[str] = []
            if encoder_id in available:
                idx = available.index(encoder_id)
                _fallback_chain = available[idx + 1:]
            elif encoder_id != "libx264":
                _fallback_chain = [e for e in available if e != encoder_id]
            # Ensure libx264 is always at the end
            if "libx264" not in _fallback_chain:
                _fallback_chain.append("libx264")

            proc = _launch_ffmpeg(encoder_id)

            def _kill_proc(p: subprocess.Popen) -> None:
                """Safely terminate an ffmpeg process and close its pipes."""
                if p is None:
                    return
                try:
                    if p.stdin and not p.stdin.closed:
                        p.stdin.close()
                except OSError:
                    pass
                try:
                    p.kill()
                    p.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                try:
                    if p.stderr and not p.stderr.closed:
                        p.stderr.close()
                except OSError:
                    pass

            # Check for immediate launch failure
            import time as _time
            _time.sleep(0.1)
            if proc.poll() is not None and encoder_id != "libx264":
                stderr_early = proc.stderr.read().decode(errors="replace")[:500] if proc.stderr else ""
                logger.warning(
                    "Encoder %s failed immediately (%s)",
                    encoder_id, stderr_early.strip(),
                )
                # Try next in fallback chain
                launched = False
                for fallback_id in _fallback_chain:
                    fb_name = encoder_display_name(fallback_id)
                    self.status.emit(f"{encoder_display_name(encoder_id)} failed, trying {fb_name}\u2026")
                    logger.info("Trying fallback encoder: %s", fallback_id)
                    encoder_id = fallback_id
                    _kill_proc(proc)
                    proc = _launch_ffmpeg(encoder_id)
                    _time.sleep(0.1)
                    if proc.poll() is None:
                        launched = True
                        break
                    else:
                        logger.warning("Fallback encoder %s also failed immediately", encoder_id)
                if not launched:
                    _kill_proc(proc)
                    self.error.emit("All encoders failed to launch")
                    return

            pipe_ok = _encode_frames(proc)

            proc.stdin.close()
            self.status.emit("Finalizing…")
            try:
                stderr_out = proc.communicate(timeout=60)[1]
            except subprocess.TimeoutExpired:
                proc.kill()
                stderr_out = proc.communicate()[1]

            stderr_text = stderr_out.decode(errors="replace") if stderr_out else ""

            # If encoder failed mid-stream, try fallback chain
            if (proc.returncode != 0 or not pipe_ok) and encoder_id != "libx264":
                failed_id = encoder_id
                logger.warning(
                    "Encoder %s failed mid-export (rc=%s): %s",
                    failed_id, proc.returncode, stderr_text[:300].strip(),
                )
                # Try remaining encoders in fallback chain
                remaining = _fallback_chain[_fallback_chain.index(failed_id) + 1:] if failed_id in _fallback_chain else _fallback_chain
                if not remaining:
                    remaining = ["libx264"]

                for fallback_id in remaining:
                    fb_name = encoder_display_name(fallback_id)
                    self.status.emit(f"{encoder_display_name(failed_id)} failed mid-export, trying {fb_name}\u2026")
                    encoder_id = fallback_id
                    _kill_proc(proc)
                    proc = _launch_ffmpeg(encoder_id)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    pipe_ok = _encode_frames(proc)
                    proc.stdin.close()
                    try:
                        stderr_out = proc.communicate(timeout=60)[1]
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        stderr_out = proc.communicate()[1]
                    stderr_text = stderr_out.decode(errors="replace") if stderr_out else ""
                    if proc.returncode == 0 and pipe_ok:
                        break  # success
                    failed_id = encoder_id
                    logger.warning("Fallback encoder %s also failed (rc=%s)", encoder_id, proc.returncode)

            if proc.returncode != 0:
                err_msg = stderr_text.strip()[-800:] if stderr_text else "Unknown ffmpeg error"
                logger.error("Export failed (encoder=%s, rc=%s): %s", encoder_id, proc.returncode, err_msg)
                self.error.emit(f"ffmpeg error ({encoder_id}): {err_msg[:500]}")
                return

            if encoder_id != original_encoder_id:
                logger.info("Export completed with fallback encoder %s (originally %s)", encoder_id, original_encoder_id)

            self.progress.emit(1.0)
            self.finished.emit(output_path)

        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            # Ensure cv2.VideoCapture is released
            if cap is not None:
                try:
                    cap.release()
                    logger.debug("cv2.VideoCapture released")
                except Exception as e:
                    logger.warning("Failed to release cv2.VideoCapture: %s", e)
            # Ensure ffmpeg process is not leaked on any error path
            if proc is not None and proc.poll() is None:
                logger.warning("Cleaning up orphaned ffmpeg process (pid=%s)", proc.pid)
                _kill_proc(proc)
            # Clean up merged voiceover temp file
            if _merged_audio_path and os.path.isfile(_merged_audio_path):
                try:
                    os.remove(_merged_audio_path)
                except OSError:
                    pass
