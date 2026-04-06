"""Keystroke overlay renderer — draws keystroke overlays on video frames.

Provides both QPainter-based (for live preview) and numpy/OpenCV-based
(for export) keystroke rendering using the recorded key event data.
Displays keystrokes as floating badges or text with configurable position,
style, and duration.
"""

import logging
from typing import List, Optional, Tuple
import ctypes.wintypes as wintypes

import cv2
import numpy as np

from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QBrush,
    QFont,
)

from .models import KeyEvent

logger = logging.getLogger(__name__)


# ── Keystroke appearance ────────────────────────────────────────────

KEYSTROKE_BG_COLOR = (50, 45, 75)        # purple-gray badge background (RGB)
KEYSTROKE_BG_COLOR_BGR = (75, 45, 50)   # purple-gray in BGR for OpenCV
KEYSTROKE_TEXT_COLOR = (255, 255, 255)  # white text (RGB)
KEYSTROKE_TEXT_COLOR_BGR = (255, 255, 255)  # white text in BGR
KEYSTROKE_OPACITY = 0.9                  # badge opacity (0-1)

# Windows virtual key code to display name mapping
_VK_NAMES = {
    0x08: "Backspace",
    0x09: "Tab",
    0x0D: "Enter",
    0x10: "Shift",
    0x11: "Ctrl",
    0x12: "Alt",
    0x13: "Pause",
    0x14: "Caps",
    0x1B: "Esc",
    0x20: "Space",
    0x21: "PgUp",
    0x22: "PgDn",
    0x23: "End",
    0x24: "Home",
    0x25: "←",
    0x26: "↑",
    0x27: "→",
    0x28: "↓",
    0x2C: "PrtSc",
    0x2D: "Ins",
    0x2E: "Del",
    # 0-9 keys
    **{k: chr(k) for k in range(0x30, 0x3A)},
    # A-Z keys
    **{k: chr(k) for k in range(0x41, 0x5B)},
    # Numpad
    0x60: "Num0", 0x61: "Num1", 0x62: "Num2", 0x63: "Num3", 0x64: "Num4",
    0x65: "Num5", 0x66: "Num6", 0x67: "Num7", 0x68: "Num8", 0x69: "Num9",
    0x6A: "*", 0x6B: "+", 0x6D: "-", 0x6E: ".", 0x6F: "/",
    # F1-F12
    **{k: f"F{k - 0x6F}" for k in range(0x70, 0x7C)},
    0x90: "NumLock",
    0x91: "Scroll",
    0xA0: "LShift",
    0xA1: "RShift",
    0xA2: "LCtrl",
    0xA3: "RCtrl",
    0xA4: "LAlt",
    0xA5: "RAlt",
    # OEM keys
    0xBA: ";",
    0xBB: "=",
    0xBC: ",",
    0xBD: "-",
    0xBE: ".",
    0xBF: "/",
    0xC0: "`",
    0xDB: "[",
    0xDC: "\\",
    0xDD: "]",
    0xDE: "'",
}


def _format_key_event(vk_code: int) -> str:
    """Convert a virtual key code to a display string.
    
    Args:
        vk_code: Windows virtual key code
        
    Returns:
        Human-readable key name (e.g., "A", "Enter", "Ctrl")
    """
    return _VK_NAMES.get(vk_code, f"VK{vk_code:02X}")


def _group_keystrokes(
    key_events: List[KeyEvent],
    timestamp_ms: float,
    display_duration_ms: int,
) -> List[Tuple[str, float, float]]:
    """Group recent keystrokes into display strings.
    
    Groups rapid successive keystrokes that occur within a short window
    into combo displays (e.g., "Ctrl+C" or "Alt+Tab").
    
    Args:
        key_events: All recorded key events
        timestamp_ms: Current playback time
        display_duration_ms: How long keystrokes remain visible
        
    Returns:
        List of (display_text, timestamp, age) tuples for visible keystrokes
    """
    if not key_events:
        return []
    
    visible = []
    for event in key_events:
        age = timestamp_ms - event.timestamp
        if age < 0 or age > display_duration_ms:
            continue
        
        # Skip events without vk_code
        if not hasattr(event, 'vk_code') or event.vk_code is None:
            continue
            
        key_name = _format_key_event(event.vk_code)
        visible.append((key_name, event.timestamp, age))
    
    # Group keystrokes that are close together (within 100ms)
    if not visible:
        return []
    
    grouped = []
    current_group = [visible[0][0]]
    group_start = visible[0][1]
    
    for i in range(1, len(visible)):
        key_name, ts, _ = visible[i]
        if ts - visible[i-1][1] < 100:  # 100ms window for grouping
            current_group.append(key_name)
        else:
            # Finalize current group
            group_age = timestamp_ms - group_start
            grouped.append(("+".join(current_group), group_start, group_age))
            current_group = [key_name]
            group_start = ts
    
    # Don't forget the last group
    if current_group:
        group_age = timestamp_ms - group_start
        grouped.append(("+".join(current_group), group_start, group_age))
    
    return grouped


def _compute_fade_alpha(age_ms: float, display_duration_ms: int) -> float:
    """Compute fade-in/fade-out alpha based on keystroke age.
    
    Args:
        age_ms: Time since keystroke occurred
        display_duration_ms: Total display duration
        
    Returns:
        Alpha value between 0.0 and 1.0
    """
    fade_in_ms = 50   # Quick fade in
    fade_out_ms = 300  # Longer fade out
    
    if age_ms < fade_in_ms:
        # Fade in
        return age_ms / fade_in_ms
    elif age_ms > display_duration_ms - fade_out_ms:
        # Fade out
        return max(0.0, (display_duration_ms - age_ms) / fade_out_ms)
    else:
        # Fully visible
        return 1.0


# ── QPainter-based keystroke rendering (for live preview) ──────────


def draw_keystrokes_qpainter(
    painter: QPainter,
    key_events: List[KeyEvent],
    timestamp_ms: float,
    config,  # KeystrokeOverlayConfig
    monitor_rect: dict,
    screen_rect_x: float,
    screen_rect_y: float,
    screen_rect_w: float,
    screen_rect_h: float,
) -> None:
    """Draw keystroke overlays on the preview compositor's screen area.
    
    Args:
        painter: QPainter instance for drawing
        key_events: All recorded key events
        timestamp_ms: Current playback time
        config: KeystrokeOverlayConfig with display settings
        monitor_rect: dict with left/top/width/height of captured monitor
        screen_rect_*: pixel position of screen area in painter coordinates
    """
    if not config.enabled or not key_events:
        return
    
    grouped = _group_keystrokes(key_events, timestamp_ms, config.display_duration_ms)
    if not grouped:
        return
    
    # Compute base position
    if config.position == "bottom-center":
        base_x = screen_rect_x + screen_rect_w / 2
        base_y = screen_rect_y + screen_rect_h - 40
    elif config.position == "bottom-left":
        base_x = screen_rect_x + 40
        base_y = screen_rect_y + screen_rect_h - 40
    else:  # near-cursor (use last keystroke position if available)
        # For simplicity in preview, default to bottom-center
        base_x = screen_rect_x + screen_rect_w / 2
        base_y = screen_rect_y + screen_rect_h - 40
    
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    
    # Draw each visible keystroke group
    y_offset = 0.0
    for text, _, age in grouped:
        alpha = _compute_fade_alpha(age, config.display_duration_ms)
        if alpha < 0.01:
            continue
        
        # Set up font
        font = QFont("Segoe UI", config.font_size, QFont.Weight.Medium)
        painter.setFont(font)
        
        # Measure text
        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(text)
        
        # Badge dimensions
        padding_x = 16
        padding_y = 8
        badge_w = text_rect.width() + padding_x * 2
        badge_h = text_rect.height() + padding_y * 2
        
        # Position badge
        if config.position == "bottom-center":
            badge_x = base_x - badge_w / 2
        else:
            badge_x = base_x
        badge_y = base_y - y_offset - badge_h
        
        # Draw badge background
        bg_alpha = int(255 * alpha * config.opacity)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(*KEYSTROKE_BG_COLOR, bg_alpha)))
        
        if config.style == "floating-badge":
            # Rounded rectangle
            badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)
            painter.drawRoundedRect(badge_rect, 8, 8)
        elif config.style == "key-cap":
            # Key-like appearance with slight 3D effect
            badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)
            painter.drawRoundedRect(badge_rect, 4, 4)
            # Draw inner highlight
            highlight_rect = QRectF(badge_x + 2, badge_y + 2, badge_w - 4, badge_h / 2)
            painter.setBrush(QBrush(QColor(255, 255, 255, int(30 * alpha))))
            painter.drawRoundedRect(highlight_rect, 2, 2)
        else:  # minimal-text
            # Just text with subtle background
            badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)
            painter.drawRoundedRect(badge_rect, 4, 4)
        
        # Draw text
        text_alpha = int(255 * alpha)
        painter.setPen(QPen(QColor(*KEYSTROKE_TEXT_COLOR, text_alpha)))
        text_x = badge_x + padding_x
        text_y = badge_y + padding_y + text_rect.height()
        painter.drawText(QPointF(text_x, text_y), text)
        
        # Stack vertically
        y_offset += badge_h + 8


# ── OpenCV/numpy-based keystroke rendering (for export) ────────────


def draw_keystrokes_cv(
    frame_bgr: np.ndarray,
    key_events: List[KeyEvent],
    timestamp_ms: float,
    config,  # KeystrokeOverlayConfig
    mon_left: int,
    mon_top: int,
    mon_w: int,
    mon_h: int,
) -> None:
    """Draw keystroke overlays onto *frame_bgr* in-place for video export.
    
    Args:
        frame_bgr: The raw video frame (same resolution as monitor)
        key_events: All recorded key events
        timestamp_ms: Current playback time
        config: KeystrokeOverlayConfig with display settings
        mon_left: Monitor left position
        mon_top: Monitor top position
        mon_w: Monitor width
        mon_h: Monitor height
    """
    if not config.enabled or not key_events:
        return
    
    grouped = _group_keystrokes(key_events, timestamp_ms, config.display_duration_ms)
    if not grouped:
        return
    
    fh, fw = frame_bgr.shape[:2]
    
    # Compute base position
    if config.position == "bottom-center":
        base_x = fw // 2
        base_y = fh - 60
    elif config.position == "bottom-left":
        base_x = 60
        base_y = fh - 60
    else:  # near-cursor
        # Default to bottom-center for export
        base_x = fw // 2
        base_y = fh - 60
    
    # Font settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = config.font_size / 18.0  # Base scale
    font_thickness = max(1, int(font_scale * 2))
    
    # Draw each visible keystroke group
    y_offset = 0
    for text, _, age in grouped:
        alpha = _compute_fade_alpha(age, config.display_duration_ms)
        if alpha < 0.01:
            continue
        
        # Measure text
        (text_w, text_h), baseline = cv2.getTextSize(
            text, font, font_scale, font_thickness
        )
        
        # Badge dimensions
        padding_x = 24
        padding_y = 12
        badge_w = text_w + padding_x * 2
        badge_h = text_h + padding_y * 2 + baseline
        
        # Position badge
        if config.position == "bottom-center":
            badge_x = base_x - badge_w // 2
        else:
            badge_x = base_x
        badge_y = base_y - y_offset - badge_h
        
        # Ensure badge is within frame bounds
        badge_x = max(10, min(badge_x, fw - badge_w - 10))
        badge_y = max(10, min(badge_y, fh - badge_h - 10))
        
        # Create badge overlay
        overlay = frame_bgr.copy()
        
        # Draw badge background
        bg_alpha_val = int(alpha * config.opacity * 255)
        if config.style == "floating-badge":
            # Rounded rectangle (approximate with ellipse corners)
            cv2.rectangle(
                overlay,
                (badge_x, badge_y),
                (badge_x + badge_w, badge_y + badge_h),
                KEYSTROKE_BG_COLOR_BGR,
                -1,
            )
        elif config.style == "key-cap":
            # Key-like appearance
            cv2.rectangle(
                overlay,
                (badge_x, badge_y),
                (badge_x + badge_w, badge_y + badge_h),
                KEYSTROKE_BG_COLOR_BGR,
                -1,
            )
            # Inner highlight
            highlight_h = badge_h // 3
            highlight_overlay = overlay.copy()
            cv2.rectangle(
                highlight_overlay,
                (badge_x + 3, badge_y + 3),
                (badge_x + badge_w - 3, badge_y + highlight_h),
                (100, 90, 110),
                -1,
            )
            # Blend highlight
            cv2.addWeighted(overlay, 0.9, highlight_overlay, 0.1, 0, overlay)
        else:  # minimal-text
            cv2.rectangle(
                overlay,
                (badge_x, badge_y),
                (badge_x + badge_w, badge_y + badge_h),
                KEYSTROKE_BG_COLOR_BGR,
                -1,
            )
        
        # Blend badge with frame using alpha
        blend_alpha = alpha * config.opacity
        np.copyto(
            frame_bgr[badge_y:badge_y + badge_h, badge_x:badge_x + badge_w],
            cv2.addWeighted(
                frame_bgr[badge_y:badge_y + badge_h, badge_x:badge_x + badge_w],
                1 - blend_alpha,
                overlay[badge_y:badge_y + badge_h, badge_x:badge_x + badge_w],
                blend_alpha,
                0,
            )
        )
        
        # Draw text
        text_x = badge_x + padding_x
        text_y = badge_y + padding_y + text_h
        cv2.putText(
            frame_bgr,
            text,
            (text_x, text_y),
            font,
            font_scale,
            KEYSTROKE_TEXT_COLOR_BGR,
            font_thickness,
            cv2.LINE_AA,
        )
        
        # Stack vertically
        y_offset += badge_h + 12
