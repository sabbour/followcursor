"""Annotation renderer — draws text, arrow, and highlight annotations on video frames.

Provides both QPainter-based (for live preview) and numpy/OpenCV-based
(for export) annotation rendering using the recorded annotation data.
Renders annotations at their specified positions for their active time range.
"""

import logging
import math
from typing import Optional

import cv2
import numpy as np

from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QBrush,
    QFont,
    QPainterPath,
    QPolygonF,
)

from .models import TextAnnotation, ArrowAnnotation, HighlightBox, AnnotationCollection

logger = logging.getLogger(__name__)


# ── QPainter-based annotation rendering (for live preview) ─────────


def render_annotations_qpainter(
    painter: QPainter,
    annotations: Optional[AnnotationCollection],
    timestamp_ms: float,
    monitor_rect: dict,
    screen_rect_x: float,
    screen_rect_y: float,
    screen_rect_w: float,
    screen_rect_h: float,
) -> None:
    """Draw annotations on the preview compositor's screen area.
    
    Renders annotations in the order: highlights → arrows → text (back to front).
    
    Args:
        painter: QPainter instance for drawing
        annotations: All annotations in the session
        timestamp_ms: Current playback time
        monitor_rect: dict with left/top/width/height of captured monitor
        screen_rect_*: pixel position of screen area in painter coordinates
    """
    if not annotations:
        return
    
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    # Render highlights first (back layer)
    if annotations.highlights:
        for highlight in annotations.highlights:
            if highlight.start_ms <= timestamp_ms <= highlight.end_ms:
                _draw_highlight_qpainter(
                    painter, highlight, screen_rect_x, screen_rect_y,
                    screen_rect_w, screen_rect_h
                )
    
    # Render arrows (middle layer)
    if annotations.arrows:
        for arrow in annotations.arrows:
            if arrow.start_ms <= timestamp_ms <= arrow.end_ms:
                _draw_arrow_qpainter(
                    painter, arrow, screen_rect_x, screen_rect_y,
                    screen_rect_w, screen_rect_h
                )
    
    # Render text (front layer)
    if annotations.texts:
        for text in annotations.texts:
            if text.start_ms <= timestamp_ms <= text.end_ms:
                _draw_text_qpainter(
                    painter, text, screen_rect_x, screen_rect_y,
                    screen_rect_w, screen_rect_h
                )


def _draw_highlight_qpainter(
    painter: QPainter,
    highlight: HighlightBox,
    screen_x: float,
    screen_y: float,
    screen_w: float,
    screen_h: float,
) -> None:
    """Draw a single highlight box annotation."""
    # Convert normalized coords to screen pixels
    px = screen_x + highlight.x * screen_w
    py = screen_y + highlight.y * screen_h
    pw = highlight.width * screen_w
    ph = highlight.height * screen_h
    
    # Fill color with opacity
    fill_color = QColor(*highlight.color)
    fill_color.setAlphaF(highlight.opacity)
    
    # Draw filled rectangle
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(fill_color))
    painter.drawRect(QRectF(px, py, pw, ph))
    
    # Draw border
    if highlight.border_width > 0:
        border_color = QColor(
            highlight.color[0],
            highlight.color[1],
            highlight.color[2],
            255  # Full opacity for border
        )
        painter.setPen(QPen(border_color, highlight.border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(px, py, pw, ph))


def _draw_arrow_qpainter(
    painter: QPainter,
    arrow: ArrowAnnotation,
    screen_x: float,
    screen_y: float,
    screen_w: float,
    screen_h: float,
) -> None:
    """Draw a single arrow annotation with arrowhead."""
    # Convert normalized coords to screen pixels
    x1 = screen_x + arrow.x1 * screen_w
    y1 = screen_y + arrow.y1 * screen_h
    x2 = screen_x + arrow.x2 * screen_w
    y2 = screen_y + arrow.y2 * screen_h
    
    color = QColor(*arrow.color)
    
    # Draw main line
    painter.setPen(QPen(color, arrow.thickness, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    
    # Draw arrowhead
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy)
    if length < 0.1:
        return  # Too short to draw arrowhead
    
    # Normalize direction vector
    dx /= length
    dy /= length
    
    # Perpendicular vector
    px = -dy
    py = dx
    
    # Arrowhead points
    head_len = arrow.head_size
    head_w = arrow.head_size * 0.6
    
    tip = QPointF(x2, y2)
    left = QPointF(x2 - dx * head_len + px * head_w, y2 - dy * head_len + py * head_w)
    right = QPointF(x2 - dx * head_len - px * head_w, y2 - dy * head_len - py * head_w)
    
    path = QPainterPath()
    path.moveTo(tip)
    path.lineTo(left)
    path.lineTo(right)
    path.closeSubpath()
    
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(color))
    painter.drawPath(path)


def _draw_text_qpainter(
    painter: QPainter,
    text: TextAnnotation,
    screen_x: float,
    screen_y: float,
    screen_w: float,
    screen_h: float,
) -> None:
    """Draw a single text annotation with optional background."""
    # Convert normalized coords to screen pixels
    px = screen_x + text.x * screen_w
    py = screen_y + text.y * screen_h
    
    # Set up font
    font = QFont("Segoe UI", text.font_size, QFont.Weight.Medium)
    painter.setFont(font)
    
    # Measure text
    fm = painter.fontMetrics()
    text_rect = fm.boundingRect(text.text)
    
    # Badge dimensions with padding
    padding_x = 12
    padding_y = 8
    badge_w = text_rect.width() + padding_x * 2
    badge_h = text_rect.height() + padding_y * 2
    
    # Center the badge on the position
    badge_x = px - badge_w / 2
    badge_y = py - badge_h / 2
    
    # Draw background if specified
    if text.background_color is not None:
        bg_color = QColor(*text.background_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 6, 6)
    
    # Draw text
    text_color = QColor(*text.color)
    painter.setPen(QPen(text_color))
    text_x = badge_x + padding_x
    text_y = badge_y + padding_y + text_rect.height()
    painter.drawText(QPointF(text_x, text_y), text.text)


# ── OpenCV/numpy-based annotation rendering (for export) ───────────


def render_annotations_cv(
    frame_bgr: np.ndarray,
    annotations: Optional[AnnotationCollection],
    timestamp_ms: float,
    source_w: int,
    source_h: int,
) -> None:
    """Draw annotations onto *frame_bgr* in-place for video export.
    
    Renders annotations in the order: highlights → arrows → text (back to front).
    
    Args:
        frame_bgr: The raw video frame (BGR format)
        annotations: All annotations in the session
        timestamp_ms: Current playback time
        source_w: Source video width (for normalizing coordinates)
        source_h: Source video height (for normalizing coordinates)
    """
    if not annotations:
        return
    
    fh, fw = frame_bgr.shape[:2]
    
    # Render highlights first (back layer)
    if annotations.highlights:
        for highlight in annotations.highlights:
            if highlight.start_ms <= timestamp_ms <= highlight.end_ms:
                _draw_highlight_cv(frame_bgr, highlight, fw, fh)
    
    # Render arrows (middle layer)
    if annotations.arrows:
        for arrow in annotations.arrows:
            if arrow.start_ms <= timestamp_ms <= arrow.end_ms:
                _draw_arrow_cv(frame_bgr, arrow, fw, fh)
    
    # Render text (front layer)
    if annotations.texts:
        for text in annotations.texts:
            if text.start_ms <= timestamp_ms <= text.end_ms:
                _draw_text_cv(frame_bgr, text, fw, fh)


def _draw_highlight_cv(
    frame_bgr: np.ndarray,
    highlight: HighlightBox,
    frame_w: int,
    frame_h: int,
) -> None:
    """Draw a single highlight box annotation."""
    # Convert normalized coords to frame pixels
    px = int(highlight.x * frame_w)
    py = int(highlight.y * frame_h)
    pw = int(highlight.width * frame_w)
    ph = int(highlight.height * frame_h)
    
    # Ensure bounds are within frame
    px = max(0, min(px, frame_w - 1))
    py = max(0, min(py, frame_h - 1))
    pw = min(pw, frame_w - px)
    ph = min(ph, frame_h - py)
    
    if pw <= 0 or ph <= 0:
        return
    
    # Create overlay for alpha blending
    overlay = frame_bgr.copy()
    
    # Convert RGBA to BGR
    color_bgr = (highlight.color[2], highlight.color[1], highlight.color[0])
    
    # Draw filled rectangle on overlay
    cv2.rectangle(overlay, (px, py), (px + pw, py + ph), color_bgr, -1)
    
    # Blend with original frame using opacity
    alpha = highlight.opacity
    roi = frame_bgr[py:py + ph, px:px + pw]
    roi_overlay = overlay[py:py + ph, px:px + pw]
    blended = cv2.addWeighted(roi, 1 - alpha, roi_overlay, alpha, 0)
    np.copyto(roi, blended)
    
    # Draw border
    if highlight.border_width > 0:
        cv2.rectangle(
            frame_bgr,
            (px, py),
            (px + pw, py + ph),
            color_bgr,
            highlight.border_width,
            cv2.LINE_AA
        )


def _draw_arrow_cv(
    frame_bgr: np.ndarray,
    arrow: ArrowAnnotation,
    frame_w: int,
    frame_h: int,
) -> None:
    """Draw a single arrow annotation with arrowhead."""
    # Convert normalized coords to frame pixels
    x1 = int(arrow.x1 * frame_w)
    y1 = int(arrow.y1 * frame_h)
    x2 = int(arrow.x2 * frame_w)
    y2 = int(arrow.y2 * frame_h)
    
    # Convert RGBA to BGR
    color_bgr = (arrow.color[2], arrow.color[1], arrow.color[0])
    
    # Draw main arrow line with arrowhead
    cv2.arrowedLine(
        frame_bgr,
        (x1, y1),
        (x2, y2),
        color_bgr,
        arrow.thickness,
        cv2.LINE_AA,
        tipLength=0.15  # Arrow tip length as fraction of line length
    )


def _draw_text_cv(
    frame_bgr: np.ndarray,
    text: TextAnnotation,
    frame_w: int,
    frame_h: int,
) -> None:
    """Draw a single text annotation with optional background."""
    # Convert normalized coords to frame pixels
    px = int(text.x * frame_w)
    py = int(text.y * frame_h)
    
    # Font settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = text.font_size / 18.0  # Base scale
    font_thickness = max(1, int(font_scale * 2))
    
    # Measure text
    (text_w, text_h), baseline = cv2.getTextSize(
        text.text, font, font_scale, font_thickness
    )
    
    # Badge dimensions with padding
    padding_x = 18
    padding_y = 12
    badge_w = text_w + padding_x * 2
    badge_h = text_h + padding_y * 2 + baseline
    
    # Center the badge on the position
    badge_x = px - badge_w // 2
    badge_y = py - badge_h // 2
    
    # Ensure badge is within frame bounds
    badge_x = max(0, min(badge_x, frame_w - badge_w))
    badge_y = max(0, min(badge_y, frame_h - badge_h))
    
    # Draw background if specified
    if text.background_color is not None:
        # Create overlay for alpha blending
        overlay = frame_bgr.copy()
        bg_color_bgr = (
            text.background_color[2],
            text.background_color[1],
            text.background_color[0]
        )
        
        # Draw rounded rectangle (approximate with regular rectangle)
        cv2.rectangle(
            overlay,
            (badge_x, badge_y),
            (badge_x + badge_w, badge_y + badge_h),
            bg_color_bgr,
            -1
        )
        
        # Blend with original frame using background alpha
        bg_alpha = text.background_color[3] / 255.0
        roi = frame_bgr[badge_y:badge_y + badge_h, badge_x:badge_x + badge_w]
        roi_overlay = overlay[badge_y:badge_y + badge_h, badge_x:badge_x + badge_w]
        blended = cv2.addWeighted(roi, 1 - bg_alpha, roi_overlay, bg_alpha, 0)
        np.copyto(roi, blended)
    
    # Draw text
    text_color_bgr = (text.color[2], text.color[1], text.color[0])
    text_x = badge_x + padding_x
    text_y = badge_y + padding_y + text_h
    
    cv2.putText(
        frame_bgr,
        text.text,
        (text_x, text_y),
        font,
        font_scale,
        text_color_bgr,
        font_thickness,
        cv2.LINE_AA
    )
