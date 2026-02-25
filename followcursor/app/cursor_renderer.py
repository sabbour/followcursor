"""Mouse cursor renderer — draws a cursor overlay on video frames.

Provides both QPainter-based (for live preview) and numpy/OpenCV-based
(for export) cursor drawing using the recorded mouse track data.
Also renders click ripple effects at recorded click positions.
"""

from typing import List, Optional, Tuple

import cv2
import numpy as np

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
)

from .models import MousePosition, ClickEvent


# ── Cursor appearance ───────────────────────────────────────────────

CURSOR_COLOR = (255, 255, 255)       # white  (RGB for QPainter, BGR for CV)
CURSOR_OUTLINE = (30, 30, 30)        # near-black outline (softer than pure black)
CURSOR_OUTLINE_W = 2.0               # outline width
CURSOR_SHADOW_ALPHA = 80             # drop shadow opacity (0-255)

# ── Click effect appearance ─────────────────────────────────────────

CLICK_DURATION_MS = 400.0            # how long the click ripple is visible
CLICK_COLOR = (138, 92, 246)         # purple (#8b5cf6) in RGB
CLICK_COLOR_BGR = (246, 92, 138)     # purple in BGR for OpenCV
CLICK_MAX_RADIUS = 24.0              # max ripple radius (preview, scaled)


def _interp_mouse(track: List[MousePosition], time_ms: float) -> Optional[Tuple[float, float]]:
    """Interpolate mouse position at *time_ms* from recorded track.

    Returns (x, y) in absolute screen coordinates, or None if no data.
    """
    if not track:
        return None
    if time_ms <= track[0].timestamp:
        return track[0].x, track[0].y
    if time_ms >= track[-1].timestamp:
        return track[-1].x, track[-1].y

    # Binary search for the right interval
    lo, hi = 0, len(track) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if track[mid].timestamp <= time_ms:
            lo = mid
        else:
            hi = mid

    a, b = track[lo], track[hi]
    dt = b.timestamp - a.timestamp
    if dt <= 0:
        return a.x, a.y
    t = (time_ms - a.timestamp) / dt
    return a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t


# ── Classic arrow cursor shape (normalized, tip at 0,0) ─────────────
# Points define a standard Windows-style pointer arrow, normalized
# so that the full height = 1.0 and width is proportional.

_ARROW_POINTS = [
    (0.00, 0.00),    # tip (hotspot)
    (0.00, 1.00),    # left edge bottom
    (0.22, 0.74),    # notch entry
    (0.42, 1.08),    # lower arm
    (0.56, 0.96),    # arm tip
    (0.32, 0.63),    # inner notch
    (0.60, 0.63),    # right wing tip
]


# ── QPainter-based cursor (for live preview) ───────────────────────


def draw_cursor_qpainter(
    painter: QPainter,
    track: List[MousePosition],
    time_ms: float,
    monitor_rect: dict,
    screen_rect_x: float,
    screen_rect_y: float,
    screen_rect_w: float,
    screen_rect_h: float,
) -> None:
    """Draw a cursor on the preview compositor's screen area.

    *monitor_rect* = dict with left/top/width/height of the captured monitor.
    *screen_rect_*  = pixel position of the screen area in painter coordinates.
    """
    pos = _interp_mouse(track, time_ms)
    if pos is None:
        return

    mx, my = pos
    mon_w = max(monitor_rect.get("width", 1), 1)
    mon_h = max(monitor_rect.get("height", 1), 1)
    mon_left = monitor_rect.get("left", 0)
    mon_top = monitor_rect.get("top", 0)

    # Normalize to 0-1 within the monitor
    nx = (mx - mon_left) / mon_w
    ny = (my - mon_top) / mon_h

    # Map to screen rect in painter coords
    px = screen_rect_x + nx * screen_rect_w
    py = screen_rect_y + ny * screen_rect_h

    # Cursor size scales with screen rect
    cs = max(14.0, screen_rect_h * 0.032)

    path = QPainterPath()
    pts = _ARROW_POINTS
    path.moveTo(px + pts[0][0] * cs, py + pts[0][1] * cs)
    for ax, ay in pts[1:]:
        path.lineTo(px + ax * cs, py + ay * cs)
    path.closeSubpath()

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Drop shadow (offset + translucent)
    shadow_off = max(1.5, cs * 0.08)
    shadow_path = QPainterPath()
    shadow_path.moveTo(px + pts[0][0] * cs + shadow_off, py + pts[0][1] * cs + shadow_off)
    for ax, ay in pts[1:]:
        shadow_path.lineTo(px + ax * cs + shadow_off, py + ay * cs + shadow_off)
    shadow_path.closeSubpath()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(0, 0, 0, CURSOR_SHADOW_ALPHA)))
    painter.drawPath(shadow_path)

    # Outline
    outline_w = max(CURSOR_OUTLINE_W, cs * 0.07)
    painter.setPen(QPen(QColor(*CURSOR_OUTLINE), outline_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(QBrush(QColor(*CURSOR_COLOR)))
    painter.drawPath(path)


# ── OpenCV/numpy-based cursor (for export) ─────────────────────────


def _build_cursor_template(height: int) -> Tuple[np.ndarray, np.ndarray]:
    """Pre-render a cursor image + alpha mask at the given pixel height.

    Returns (cursor_bgr, cursor_alpha) both of shape (H, W).
    The cursor tip is at (0, 0) in the returned image.
    Includes a soft drop shadow for depth.
    """
    h = max(height, 8)
    w = int(h * 0.7) + 2  # ensure enough width
    shadow_off = max(2, int(h * 0.08))
    pad = shadow_off + 4  # extra padding for shadow

    cursor_bgra = np.zeros((h + pad * 2, w + pad * 2, 4), dtype=np.uint8)

    pts = np.array(
        [[int(p[0] * h) + pad, int(p[1] * h) + pad] for p in _ARROW_POINTS],
        dtype=np.int32,
    )

    # Drop shadow (offset, semi-transparent)
    shadow_pts = pts + shadow_off
    cv2.fillPoly(cursor_bgra, [shadow_pts], (0, 0, 0, CURSOR_SHADOW_ALPHA))
    # Blur the shadow channel slightly
    alpha_ch = cursor_bgra[:, :, 3].copy()
    blur_k = max(3, int(h * 0.1)) | 1  # must be odd
    alpha_ch = cv2.GaussianBlur(alpha_ch, (blur_k, blur_k), 0)
    cursor_bgra[:, :, 3] = alpha_ch

    # Outline (dark, slightly thicker)
    outline_thick = max(2, int(h * 0.09))
    cv2.fillPoly(cursor_bgra, [pts], (*CURSOR_OUTLINE[::-1], 255))
    cv2.polylines(cursor_bgra, [pts], True, (*CURSOR_OUTLINE[::-1], 255), outline_thick, cv2.LINE_AA)

    # Inner fill (white)
    cv2.fillPoly(cursor_bgra, [pts], (255, 255, 255, 255))

    # Trim to bounding box
    alpha = cursor_bgra[:, :, 3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if not rows.any():
        return np.zeros((1, 1, 3), dtype=np.uint8), np.zeros((1, 1), dtype=np.uint8)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    cropped = cursor_bgra[rmin:rmax + 1, cmin:cmax + 1]

    cursor_bgr = cropped[:, :, :3]
    cursor_alpha = cropped[:, :, 3]
    return cursor_bgr, cursor_alpha


def draw_cursor_cv(
    frame_bgr: np.ndarray,
    track: List[MousePosition],
    time_ms: float,
    mon_left: int,
    mon_top: int,
    mon_w: int,
    mon_h: int,
    cursor_bgr: np.ndarray,
    cursor_alpha: np.ndarray,
) -> None:
    """Draw cursor onto *frame_bgr* in-place.

    *frame_bgr* is the raw video frame (same resolution as monitor).
    The cursor template is pre-built via _build_cursor_template().
    """
    pos = _interp_mouse(track, time_ms)
    if pos is None:
        return

    mx, my = pos
    fh, fw = frame_bgr.shape[:2]
    ch, cw = cursor_bgr.shape[:2]

    # Position in frame pixels
    px = int((mx - mon_left) / max(mon_w, 1) * fw)
    py = int((my - mon_top) / max(mon_h, 1) * fh)

    # Bounds check
    x1, y1 = px, py
    x2, y2 = px + cw, py + ch

    # Clip to frame
    src_x1 = max(0, -x1)
    src_y1 = max(0, -y1)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(fw, x2)
    y2 = min(fh, y2)
    src_x2 = src_x1 + (x2 - x1)
    src_y2 = src_y1 + (y2 - y1)

    if x2 <= x1 or y2 <= y1:
        return

    roi = frame_bgr[y1:y2, x1:x2]
    c_roi = cursor_bgr[src_y1:src_y2, src_x1:src_x2]
    a_roi = cursor_alpha[src_y1:src_y2, src_x1:src_x2]

    alpha = a_roi[:, :, np.newaxis].astype(np.float32) / 255.0
    blended = (c_roi.astype(np.float32) * alpha + roi.astype(np.float32) * (1 - alpha))
    np.copyto(roi, blended.astype(np.uint8))


# ── QPainter-based click effects (for live preview) ────────────────


def draw_clicks_qpainter(
    painter: QPainter,
    click_events: List[ClickEvent],
    time_ms: float,
    monitor_rect: dict,
    screen_rect_x: float,
    screen_rect_y: float,
    screen_rect_w: float,
    screen_rect_h: float,
) -> None:
    """Draw expanding ripple effects for recent clicks on the preview."""
    if not click_events:
        return

    mon_w = max(monitor_rect.get("width", 1), 1)
    mon_h = max(monitor_rect.get("height", 1), 1)
    mon_left = monitor_rect.get("left", 0)
    mon_top = monitor_rect.get("top", 0)

    # Scale ripple radius with preview size
    max_r = max(CLICK_MAX_RADIUS, screen_rect_h * 0.025)

    for click in click_events:
        age = time_ms - click.timestamp
        if age < 0 or age > CLICK_DURATION_MS:
            continue

        t = age / CLICK_DURATION_MS  # 0 → 1

        # Map click position to screen rect
        nx = (click.x - mon_left) / mon_w
        ny = (click.y - mon_top) / mon_h
        px = screen_rect_x + nx * screen_rect_w
        py = screen_rect_y + ny * screen_rect_h

        # Expanding ring with fade
        radius = max_r * (0.3 + 0.7 * t)
        ring_alpha = int(220 * (1.0 - t))
        if ring_alpha > 0:
            color = QColor(*CLICK_COLOR, ring_alpha)
            pen_w = max(2.0, 3.0 * (1.0 - t))
            painter.setPen(QPen(color, pen_w))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(px, py), radius, radius)

        # Inner solid dot (fades faster)
        dot_alpha = int(200 * max(0.0, 1.0 - t * 1.8))
        if dot_alpha > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(*CLICK_COLOR, dot_alpha))
            dot_r = max(3.0, 5.0 * (1.0 - t * 0.5))
            painter.drawEllipse(QPointF(px, py), dot_r, dot_r)


# ── OpenCV/numpy-based click effects (for export) ──────────────────


def draw_clicks_cv(
    frame_bgr: np.ndarray,
    click_events: List[ClickEvent],
    time_ms: float,
    mon_left: int,
    mon_top: int,
    mon_w: int,
    mon_h: int,
) -> None:
    """Draw expanding ripple effects for recent clicks onto *frame_bgr* in-place."""
    if not click_events:
        return

    fh, fw = frame_bgr.shape[:2]
    max_r = max(20, int(fh * 0.015))

    for click in click_events:
        age = time_ms - click.timestamp
        if age < 0 or age > CLICK_DURATION_MS:
            continue

        t = age / CLICK_DURATION_MS

        # Position in frame pixels
        px = int((click.x - mon_left) / max(mon_w, 1) * fw)
        py = int((click.y - mon_top) / max(mon_h, 1) * fh)

        # Expanding ring with fade
        radius = int(max_r * (0.3 + 0.7 * t))
        ring_alpha = 1.0 - t
        if ring_alpha > 0.05:
            thickness = max(1, int(3.0 * (1.0 - t)))
            # Draw directly — small visual element, no need for alpha blending
            color_scaled = tuple(int(c * ring_alpha * 0.85) for c in CLICK_COLOR_BGR)
            cv2.circle(frame_bgr, (px, py), radius, color_scaled, thickness, cv2.LINE_AA)

        # Inner solid dot
        dot_alpha = max(0.0, 1.0 - t * 1.8)
        if dot_alpha > 0.05:
            dot_r = max(2, int(5.0 * (1.0 - t * 0.5)))
            color_dot = tuple(int(c * dot_alpha * 0.8) for c in CLICK_COLOR_BGR)
            cv2.circle(frame_bgr, (px, py), dot_r, color_dot, -1, cv2.LINE_AA)
