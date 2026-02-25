"""Export video with zoom keyframes baked in — produces H.264 MP4."""

import logging
import os
import subprocess
import threading

logger = logging.getLogger(__name__)
from typing import List, Optional

import cv2
import numpy as np

from PySide6.QtCore import QObject, Signal

from .models import ZoomKeyframe, MousePosition, ClickEvent
from .zoom_engine import ZoomEngine
from .cursor_renderer import draw_cursor_cv, draw_clicks_cv, _build_cursor_template
from .backgrounds import BackgroundPreset, DEFAULT_PRESET, WAVE_LAYERS
from .frames import FramePreset, DEFAULT_FRAME


from .utils import ffmpeg_exe as _ffmpeg_exe, subprocess_kwargs as _subprocess_kwargs, build_encoder_args as _build_encoder_args


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
                bg_canvas: np.ndarray | None = None) -> np.ndarray:
    """Fast compositor — copies pre-rendered bezel, places video in screen,
    then applies zoom.

    *zoom_video_only*=True  (No Frame): crops the source video only;
    background stays static.
    *zoom_video_only*=False (device frame): zooms the device (bezel +
    video) while the background stays static.  Requires *bg_canvas*
    (the background-only layer without bezel).
    """
    canvas = base_canvas.copy()
    fh, fw = frame_bgr.shape[:2]

    if scr_w <= 0 or scr_h <= 0:
        return canvas

    if zoom_video_only and zoom > 1.001:
        # No Frame mode: crop source video, background stays fixed
        crop_w = fw / zoom
        crop_h = fh / zoom
        cx = pan_x * fw - crop_w / 2
        cy = pan_y * fh - crop_h / 2
        cx = max(0.0, min(cx, fw - crop_w))
        cy = max(0.0, min(cy, fh - crop_h))
        x1, y1 = int(cx), int(cy)
        x2 = min(int(cx + crop_w), fw)
        y2 = min(int(cy + crop_h), fh)
        frame_bgr = frame_bgr[y1:y2, x1:x2]
        resized = cv2.resize(frame_bgr, (scr_w, scr_h),
                             interpolation=cv2.INTER_LANCZOS4)
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

        # Zoom the composed canvas (bezel + video)
        new_w = int(W * zoom)
        new_h = int(H * zoom)
        zoomed = cv2.resize(canvas, (new_w, new_h),
                            interpolation=cv2.INTER_LANCZOS4)

        # Compute offset so that (fx, fy) maps to canvas center
        ox = int(fx * zoom - W / 2)
        oy = int(fy * zoom - H / 2)
        # Clamp
        ox = max(0, min(ox, new_w - W))
        oy = max(0, min(oy, new_h - H))

        cropped_device = zoomed[oy:oy + H, ox:ox + W]

        # Composite: static background + zoomed device on top
        result = bg_canvas.copy()
        # The zoomed device region has non-background pixels; use it
        # where the base_canvas differs from bg (i.e. device area)
        # For simplicity, use the zoomed canvas but restore background
        # in the original background-only regions.
        # Since the bezel/device is opaque, we can detect device pixels
        # by comparing base_canvas vs bg_canvas.
        device_mask = np.any(base_canvas != bg_canvas, axis=2)
        # Build a zoomed device mask
        device_mask_u8 = device_mask.astype(np.uint8) * 255
        zoomed_mask = cv2.resize(device_mask_u8, (new_w, new_h),
                                 interpolation=cv2.INTER_NEAREST)
        cropped_mask = zoomed_mask[oy:oy + H, ox:ox + W]
        mask_bool = cropped_mask > 127
        np.copyto(result, cropped_device, where=mask_bool[:, :, np.newaxis])
        return result

    return canvas


class VideoExporter(QObject):
    """Reads the raw recording, applies zoom/pan per-frame, writes H.264 MP4."""

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
        output_dim=None,
        duration_ms: float = 0.0,
        frame_timestamps: Optional[List[float]] = None,
        trim_start_ms: float = 0.0,
        trim_end_ms: float = 0.0,
        encoder_id: str = "libx264",
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
        """
        self._thread = threading.Thread(
            target=self._run,
            args=(input_path, output_path, keyframes, actual_fps,
                  mouse_track or [], monitor_rect or {},
                  bg_preset or DEFAULT_PRESET,
                  frame_preset or DEFAULT_FRAME,
                  click_events or [],
                  output_dim,
                  duration_ms,
                  frame_timestamps,
                  trim_start_ms,
                  trim_end_ms,
                  encoder_id),
            daemon=True,
        )
        self._thread.start()

    # ── internal ────────────────────────────────────────────────────

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
        output_dim=None,
        duration_ms: float = 0.0,
        frame_timestamps: Optional[List[float]] = None,
        trim_start_ms: float = 0.0,
        trim_end_ms: float = 0.0,
        encoder_id: str = "libx264",
    ) -> None:
        try:
            cap = cv2.VideoCapture(input_path)
            if not cap.isOpened():
                self.error.emit(f"Cannot open {input_path}")
                return

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0 or fps > 120:
                fps = 30.0
            if actual_fps > 0:
                fps = actual_fps
            cap_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # After the post-recording remux the metadata is correct.
            # For legacy videos, detect metadata/duration mismatch and
            # recount frames if needed.
            meta_dur = (cap_frame_count / fps * 1000) if fps > 0 else 0
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
                    fps = real_frame_count / (duration_ms / 1000.0)
                total_frames = real_frame_count if real_frame_count > 0 else cap_frame_count
            else:
                total_frames = cap_frame_count
            src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if src_w == 0 or src_h == 0:
                self.error.emit("Invalid video dimensions")
                cap.release()
                return

            # Determine output canvas size
            if output_dim and output_dim != "auto" and isinstance(output_dim, (tuple, list)):
                out_w, out_h = int(output_dim[0]), int(output_dim[1])
                # Ensure even dimensions (required by H.264)
                out_w = out_w + (out_w % 2)
                out_h = out_h + (out_h % 2)
            else:
                out_w, out_h = src_w, src_h

            w, h = out_w, out_h

            # Ensure even dimensions BEFORE building background/bezel
            # (H.264 requires even dimensions; canvas must match ffmpeg -s)
            w = w + (w % 2)
            h = h + (h % 2)

            # Ensure .mp4 extension
            if not output_path.lower().endswith(".mp4"):
                output_path = output_path.rsplit(".", 1)[0] + ".mp4"

            # Pre-build the gradient background and bezel layer (once)
            bg_top_bgr, bg_bottom_bgr = _preset_to_bgr(bg_preset)
            bg = _build_background(w, h, bg_top_bgr, bg_bottom_bgr,
                                   kind=bg_preset.kind)

            fp = frame_preset

            # Compute device geometry from frame preset
            W, H = float(w), float(h)
            video_aspect = src_w / max(src_h, 1)

            if fp.is_none:
                # No frame — video fills full canvas
                if W / H > video_aspect:
                    scr_h = h
                    scr_w = int(H * video_aspect)
                else:
                    scr_w = w
                    scr_h = int(W / video_aspect)
                scr_x = (w - scr_w) // 2
                scr_y = (h - scr_h) // 2
                # Build simple bg canvas (no bezel)
                base_canvas = bg.copy()
                screen_mask = np.zeros((h, w), dtype=np.uint8)
                screen_mask[scr_y:scr_y + scr_h, scr_x:scr_x + scr_w] = 255
            else:
                pad_x = W * fp.padding
                pad_y = H * fp.padding
                avail_w = W - 2 * pad_x
                avail_h = H - 2 * pad_y

                preliminary_scale = avail_w / _BEZEL_REF_W
                bw_est = fp.bezel_width * preliminary_scale

                dev_h = avail_h
                scr_h_try = dev_h - 2 * bw_est
                scr_w_try = scr_h_try * video_aspect
                dev_w = scr_w_try + 2 * bw_est
                if dev_w > avail_w:
                    dev_w = avail_w
                    scr_w_try = dev_w - 2 * bw_est
                    scr_h_try = scr_w_try / video_aspect
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

                if bw > 0:
                    # Pre-render the bezel (bg + shadow + bezel + edge) — done once
                    base_canvas, screen_mask, _ = _build_bezel_layer(
                        h, w, bg,
                        dev_x_i, dev_y_i, dev_w_i, dev_h_i,
                        scr_x, scr_y, scr_w, scr_h,
                        outer_r, inner_r, edge_thickness,
                    )
                else:
                    # Shadow-only or zero-bezel: just shadow + rounded screen
                    base_canvas = bg.copy()
                    if fp.shadow_layers > 0 and outer_r > 0:
                        for i in range(fp.shadow_layers):
                            off = 2 + i * 2
                            shadow_mask = np.zeros((h, w), dtype=np.uint8)
                            s_pts = _rounded_rect_contour(
                                dev_x_i + int(off * 0.3), dev_y_i + off,
                                dev_w_i, dev_h_i, outer_r + 2
                            )
                            cv2.fillPoly(shadow_mask, [s_pts], 255)
                            alpha = max(40 - i * 10, 5) / 255.0
                            shadow_region = shadow_mask > 0
                            base_canvas[shadow_region] = (
                                base_canvas[shadow_region].astype(np.float32) * (1 - alpha)
                            ).astype(np.uint8)
                    screen_mask = np.zeros((h, w), dtype=np.uint8)
                    if inner_r > 0:
                        inner_pts = _rounded_rect_contour(scr_x, scr_y, scr_w, scr_h, inner_r)
                        cv2.fillPoly(screen_mask, [inner_pts], 255)
                    else:
                        screen_mask[scr_y:scr_y + scr_h, scr_x:scr_x + scr_w] = 255
                    base_canvas[screen_mask > 0] = 0

            if w < 2 or h < 2:
                self.error.emit("Output dimensions too small for encoding")
                return

            # Pipe raw BGR frames to ffmpeg for H.264 encoding
            ffmpeg = _ffmpeg_exe()
            original_encoder_id = encoder_id

            def _launch_ffmpeg(enc_id: str) -> subprocess.Popen:
                enc_args = _build_encoder_args(enc_id)
                cmd = [
                    ffmpeg, "-y",
                    "-f", "rawvideo",
                    "-vcodec", "rawvideo",
                    "-s", f"{w}x{h}",
                    "-pix_fmt", "bgr24",
                    "-r", str(fps),
                    "-i", "pipe:",
                ] + enc_args + [
                    output_path,
                ]
                logger.info("Launching ffmpeg with encoder %s: %s", enc_id, " ".join(cmd))
                return subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    **_subprocess_kwargs(),
                )

            def _encode_frames(proc: subprocess.Popen) -> bool:
                """Feed all frames to ffmpeg. Returns True on success."""
                nonlocal frame_timestamps  # read-only access

                engine = ZoomEngine()
                for kf in keyframes:
                    engine.add_keyframe(kf)

                # Pre-build cursor template for overlay
                cursor_h_px = max(16, int(h * 0.015))
                c_bgr, c_alpha = _build_cursor_template(cursor_h_px)
                m_left = monitor_rect.get("left", 0)
                m_top = monitor_rect.get("top", 0)
                m_w = max(monitor_rect.get("width", w), 1)
                m_h = max(monitor_rect.get("height", h), 1)
                _has_cursor = len(mouse_track) > 0 and m_w > 0
                _has_clicks = len(click_events) > 0 and m_w > 0

                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                f_idx = 0
                exported = 0
                last_f = None

                eff_ts = trim_start_ms if trim_start_ms > 0 else 0.0
                eff_te = trim_end_ms if trim_end_ms > 0 else (duration_ms if duration_ms > 0 else float("inf"))
                trimming = eff_ts > 0 or (trim_end_ms > 0 and trim_end_ms < (duration_ms or float("inf")))
                t_total = total_frames
                if trimming and eff_te > eff_ts:
                    t_total = max(1, int((eff_te - eff_ts) / 1000.0 * fps))

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    last_f = frame.copy()

                    if frame_timestamps and f_idx < len(frame_timestamps):
                        t_ms = frame_timestamps[f_idx]
                    else:
                        t_ms = (f_idx / fps) * 1000.0

                    f_idx += 1

                    if t_ms < eff_ts:
                        continue
                    if t_ms > eff_te:
                        break

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
                        )

                    composed = _compose_cv(
                        frame, zoom, px, py, w, h,
                        base_canvas, screen_mask,
                        scr_x, scr_y, scr_w, scr_h,
                        zoom_video_only=fp.is_none,
                        bg_canvas=bg,
                    )
                    try:
                        proc.stdin.write(composed.tobytes())
                    except (BrokenPipeError, OSError):
                        return False
                    exported += 1

                    if t_total > 0 and exported % 10 == 0:
                        self.progress.emit(min(1.0, exported / t_total))

                # Extra frames for zoom-out tail
                if last_f is not None and engine.keyframes:
                    last_kf = engine.keyframes[-1]
                    end_time = last_kf.timestamp + last_kf.duration
                    if frame_timestamps and f_idx > 0 and f_idx - 1 < len(frame_timestamps):
                        video_end_ms = frame_timestamps[f_idx - 1]
                    else:
                        video_end_ms = (f_idx / fps) * 1000.0
                    if end_time > video_end_ms:
                        extra = int((end_time - video_end_ms) / 1000.0 * fps) + 1
                        for ei in range(extra):
                            t_ms = video_end_ms + (ei / fps) * 1000.0
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
                                )
                            composed = _compose_cv(
                                fc, zoom, px, py, w, h,
                                base_canvas, screen_mask,
                                scr_x, scr_y, scr_w, scr_h,
                                zoom_video_only=fp.is_none,
                                bg_canvas=bg,
                            )
                            try:
                                proc.stdin.write(composed.tobytes())
                            except (BrokenPipeError, OSError):
                                return False

                return True

            # ── Try encoding (with HW fallback chain) ────────────────
            #
            # Build a fallback chain: try other available HW encoders
            # before falling back to software (libx264).
            from .utils import detect_available_encoders, encoder_display_name
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
                    proc = _launch_ffmpeg(encoder_id)
                    _time.sleep(0.1)
                    if proc.poll() is None:
                        launched = True
                        break
                    else:
                        logger.warning("Fallback encoder %s also failed immediately", encoder_id)
                if not launched:
                    self.error.emit("All encoders failed to launch")
                    cap.release()
                    return

            pipe_ok = _encode_frames(proc)

            proc.stdin.close()
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

            cap.release()

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
