"""Compositor — renders a screen recording inside a drawn device bezel.

Used by both the live preview widget and the video exporter so the
exported MP4 looks identical to the in-app preview.
"""

from typing import List, Optional

from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import (
    QImage,
    QPainter,
    QColor,
    QLinearGradient,
    QRadialGradient,
    QPen,
    QBrush,
    QPainterPath,
)

from .models import MousePosition
from .backgrounds import BackgroundPreset, DEFAULT_PRESET, WAVE_LAYERS
from .frames import FramePreset, DEFAULT_FRAME

# Re-export ClickEvent so compositor callers don't need to import models
from .models import ClickEvent

# ── Visual constants ────────────────────────────────────────────────

# Device frame bezel
BEZEL_COLOR     = QColor("#1a1a1a")       # dark bezel body
BEZEL_EDGE      = QColor("#6b6b6b")       # silver outer rim
BEZEL_HIGHLIGHT = QColor(255, 255, 255, 18)  # subtle top/left highlight
OUTER_RADIUS    = 18.0                     # corner radius of device
CAMERA_DOT_R    = 3.0                      # front camera
CAMERA_COLOR    = QColor("#333333")

# Padding around device frame (fraction of canvas)
DEVICE_PAD = 0.04
# Device aspect ratio — derived from video frame + bezel at runtime
# Fallback used only for empty state (no video)
DEVICE_ASPECT_FALLBACK = 16.0 / 9.0


# ── Background rendering helper ────────────────────────────────────

def _paint_bg(painter: QPainter, W: float, H: float,
              preset: BackgroundPreset) -> None:
    """Paint the background fill — solid, gradient, or pattern."""
    import math

    ct = QColor(*preset.color_top)
    cb = QColor(*preset.color_bottom)
    kind = preset.kind

    if kind == "wavy":
        # Base gradient
        grad = QLinearGradient(0, 0, W * 0.3, H)
        grad.setColorAt(0.0, ct)
        grad.setColorAt(1.0, cb)
        painter.fillRect(QRectF(0, 0, W, H), grad)

        # Overlaid sine-wave layers
        for y_frac, amp_frac, freq, phase, alpha, use_top in WAVE_LAYERS:
            wave_c = QColor(ct if use_top else cb)
            wave_c.setAlphaF(alpha)

            path = QPainterPath()
            path.moveTo(0, H)
            step = max(int(W / 300), 1)
            for x_px in range(0, int(W) + 1, step):
                t = x_px / max(W, 1)
                y = H * y_frac + H * amp_frac * math.sin(
                    2 * math.pi * freq * t + phase)
                path.lineTo(x_px, y)
            path.lineTo(W, H)
            path.closeSubpath()
            painter.fillPath(path, wave_c)

    elif kind == "radial":
        # Dark outer fill
        painter.fillRect(QRectF(0, 0, W, H), cb)
        # Radial glow from centre
        rg = QRadialGradient(W / 2, H / 2, max(W, H) * 0.6)
        rg.setColorAt(0.0, ct)
        rg.setColorAt(1.0, QColor(cb.red(), cb.green(), cb.blue(), 0))
        painter.fillRect(QRectF(0, 0, W, H), QBrush(rg))

    elif kind == "spotlight":
        # Dark fill with off-centre glow from upper-right area
        painter.fillRect(QRectF(0, 0, W, H), cb)
        rg = QRadialGradient(W * 0.8, H * 0.2, max(W, H) * 0.75)
        rg.setColorAt(0.0, ct)
        rg.setColorAt(1.0, QColor(cb.red(), cb.green(), cb.blue(), 0))
        painter.fillRect(QRectF(0, 0, W, H), QBrush(rg))

    elif kind == "gradient":
        grad = QLinearGradient(0, 0, W * 0.5, H)
        grad.setColorAt(0.0, ct)
        grad.setColorAt(1.0, cb)
        painter.fillRect(QRectF(0, 0, W, H), grad)

    else:  # solid
        painter.fillRect(QRectF(0, 0, W, H), ct)


# ── Public API ──────────────────────────────────────────────────────


def compose_scene(
    painter: QPainter,
    frame: QImage,
    canvas_w: float,
    canvas_h: float,
    zoom: float = 1.0,
    pan_x: float = 0.5,
    pan_y: float = 0.5,
    mouse_track: Optional[List[MousePosition]] = None,
    time_ms: float = 0.0,
    monitor_rect: Optional[dict] = None,
    bg_preset: Optional[BackgroundPreset] = None,
    frame_preset: Optional[FramePreset] = None,
    click_events: Optional[List[ClickEvent]] = None,
) -> None:
    """Paint the device-frame composition onto *painter*.

    Draws:  gradient background  →  device bezel  →  video inside screen
            →  mouse cursor (if mouse_track provided).

    When *zoom* > 1 the device scales up and pans so the point
    (*pan_x*, *pan_y*) in the video stays centred in the output.
    """
    W, H = float(canvas_w), float(canvas_h)
    iw, ih = frame.width(), frame.height()
    if iw <= 0 or ih <= 0:
        return

    fp = frame_preset or DEFAULT_FRAME

    # ── background ─────────────────────────────────────────────────
    preset = bg_preset or DEFAULT_PRESET
    _paint_bg(painter, W, H, preset)

    # ── fit device into canvas ──────────────────────────────────────
    video_aspect = iw / ih
    dev_pad = fp.padding

    if fp.is_none:
        # No frame — video fills the entire canvas
        scr_x, scr_y = 0.0, 0.0
        scr_w, scr_h = W, H
        # Letterbox / pillarbox to maintain aspect
        if W / H > video_aspect:
            scr_h = H
            scr_w = H * video_aspect
        else:
            scr_w = W
            scr_h = W / video_aspect
        scr_x = (W - scr_w) / 2
        scr_y = (H - scr_h) / 2
        dev_x, dev_y, dev_w, dev_h = scr_x, scr_y, scr_w, scr_h
        bw = 0.0
        outer_r = 0.0
        inner_r = 0.0
        scale = 1.0
    else:
        preliminary_scale = (W - 2 * W * dev_pad) / 900.0
        bw_est = fp.bezel_width * preliminary_scale
        pad_x = W * dev_pad
        pad_y = H * dev_pad
        avail_w = W - 2 * pad_x
        avail_h = H - 2 * pad_y

        dev_h = avail_h
        scr_h_try = dev_h - 2 * bw_est
        scr_w_try = scr_h_try * video_aspect
        dev_w = scr_w_try + 2 * bw_est
        if dev_w > avail_w:
            dev_w = avail_w
            scr_w_try = dev_w - 2 * bw_est
            scr_h_try = scr_w_try / video_aspect
            dev_h = scr_h_try + 2 * bw_est

        dev_x = (W - dev_w) / 2
        dev_y = (H - dev_h) / 2
        scale = dev_w / 900.0
        bw = fp.bezel_width * scale
        outer_r = fp.outer_radius * scale
        inner_r = fp.inner_radius * scale

        scr_x = dev_x + bw
        scr_y = dev_y + bw
        scr_w = dev_w - 2 * bw
        scr_h = dev_h - 2 * bw

    # ── zoom ─────────────────────────────────────────────────────────
    # No Frame: crop source video only (background stays static).
    # Device frame: zoom entire canvas (physical device metaphor).
    _zoom_video_only = fp.is_none
    source_rect = QRectF(0, 0, iw, ih)

    if _zoom_video_only and zoom > 1.001:
        crop_w = iw / zoom
        crop_h = ih / zoom
        cx = pan_x * iw - crop_w / 2
        cy = pan_y * ih - crop_h / 2
        cx = max(0.0, min(cx, iw - crop_w))
        cy = max(0.0, min(cy, ih - crop_h))
        source_rect = QRectF(cx, cy, crop_w, crop_h)
    elif not _zoom_video_only and zoom > 1.001:
        fx = scr_x + pan_x * scr_w
        fy = scr_y + pan_y * scr_h
        painter.translate(W / 2, H / 2)
        painter.scale(zoom, zoom)
        painter.translate(-fx, -fy)

    # ── device body (outer shell) ───────────────────────────────────
    if not fp.is_none:
        device_rect = QRectF(dev_x, dev_y, dev_w, dev_h)

        # Drop shadow
        for i in range(fp.shadow_layers):
            shadow_off = 2 + i * 2
            shadow_rect = QRectF(dev_x + shadow_off * 0.3, dev_y + shadow_off, dev_w, dev_h)
            sp = QPainterPath()
            sp.addRoundedRect(shadow_rect, outer_r + 2, outer_r + 2)
            painter.fillPath(sp, QColor(0, 0, 0, max(40 - i * 10, 5)))

        if bw > 0:
            # Outer edge + bezel body
            bezel_c = QColor(*fp.bezel_color)
            edge_c = QColor(*fp.edge_color)
            painter.setPen(QPen(edge_c, max(fp.edge_width * scale, 0.5)))
            painter.setBrush(QBrush(bezel_c))
            painter.drawRoundedRect(device_rect, outer_r, outer_r)

            # Subtle highlight on top edge
            highlight_rect = QRectF(dev_x + outer_r, dev_y + 0.5, dev_w - 2 * outer_r, 1.0)
            painter.fillRect(highlight_rect, BEZEL_HIGHLIGHT)

    # ── screen area ─────────────────────────────────────────────────
    screen_rect = QRectF(scr_x, scr_y, scr_w, scr_h)

    if inner_r > 0:
        screen_path = QPainterPath()
        screen_path.addRoundedRect(screen_rect, inner_r, inner_r)
        painter.save()
        painter.setClipPath(screen_path)
        painter.drawImage(screen_rect, frame, source_rect)
        painter.restore()
        painter.setPen(QPen(QColor(0, 0, 0, 120), max(0.5 * scale, 0.5)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(screen_rect, inner_r, inner_r)
    else:
        painter.drawImage(screen_rect, frame, source_rect)

    # ── front camera dot ────────────────────────────────────────────
    if fp.show_camera and bw > 0:
        cam_r = CAMERA_DOT_R * scale
        cam_cx = dev_x + dev_w / 2
        cam_cy = dev_y + bw / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(CAMERA_COLOR))
        painter.drawEllipse(QPointF(cam_cx, cam_cy), cam_r, cam_r)
        painter.setBrush(QBrush(QColor(80, 80, 80)))
        painter.drawEllipse(QPointF(cam_cx - cam_r * 0.2, cam_cy - cam_r * 0.2),
                            cam_r * 0.35, cam_r * 0.35)

    # ── mouse cursor overlay ───────────────────────────────────────
    if mouse_track and monitor_rect:
        from .cursor_renderer import draw_cursor_qpainter
        if _zoom_video_only and zoom > 1.001:
            # No Frame + zoom: virtual screen rect for cropped video
            src = source_rect
            vscr_w = scr_w * (iw / src.width())
            vscr_h = scr_h * (ih / src.height())
            vscr_x = scr_x - (src.x() / iw) * vscr_w
            vscr_y = scr_y - (src.y() / ih) * vscr_h
            painter.save()
            painter.setClipRect(QRectF(scr_x, scr_y, scr_w, scr_h))
            draw_cursor_qpainter(
                painter, mouse_track, time_ms, monitor_rect,
                vscr_x, vscr_y, vscr_w, vscr_h,
            )
            painter.restore()
        else:
            # Device frame (zoomed via painter transform) or no zoom
            draw_cursor_qpainter(
                painter, mouse_track, time_ms, monitor_rect,
                scr_x, scr_y, scr_w, scr_h,
            )

    # ── click effects overlay ──────────────────────────────────────
    if click_events and monitor_rect:
        from .cursor_renderer import draw_clicks_qpainter
        if _zoom_video_only and zoom > 1.001:
            src = source_rect
            vscr_w = scr_w * (iw / src.width())
            vscr_h = scr_h * (ih / src.height())
            vscr_x = scr_x - (src.x() / iw) * vscr_w
            vscr_y = scr_y - (src.y() / ih) * vscr_h
            painter.save()
            painter.setClipRect(QRectF(scr_x, scr_y, scr_w, scr_h))
            draw_clicks_qpainter(
                painter, click_events, time_ms, monitor_rect,
                vscr_x, vscr_y, vscr_w, vscr_h,
            )
            painter.restore()
        else:
            draw_clicks_qpainter(
                painter, click_events, time_ms, monitor_rect,
                scr_x, scr_y, scr_w, scr_h,
            )


def draw_empty_bg(painter: QPainter, w: float, h: float,
                   bg_preset: Optional[BackgroundPreset] = None) -> None:
    """Draw the background with an empty device frame."""
    preset = bg_preset or DEFAULT_PRESET
    _paint_bg(painter, float(w), float(h), preset)

    # Draw device with black screen
    W, H = float(w), float(h)
    pad_x = W * DEVICE_PAD
    pad_y = H * DEVICE_PAD
    avail_w = W - 2 * pad_x
    avail_h = H - 2 * pad_y

    if avail_w / max(avail_h, 1) > DEVICE_ASPECT_FALLBACK:
        dev_h = avail_h
        dev_w = dev_h * DEVICE_ASPECT_FALLBACK
    else:
        dev_w = avail_w
        dev_h = dev_w / DEVICE_ASPECT_FALLBACK

    dev_x = (W - dev_w) / 2
    dev_y = (H - dev_h) / 2
    scale = dev_w / 900.0
    outer_r = OUTER_RADIUS * scale

    device_rect = QRectF(dev_x, dev_y, dev_w, dev_h)
    painter.setPen(QPen(BEZEL_EDGE, max(1.5 * scale, 1.0)))
    painter.setBrush(QBrush(BEZEL_COLOR))
    painter.drawRoundedRect(device_rect, outer_r, outer_r)
