"""Keystroke overlay renderer — draws keystroke overlays on video frames.

Provides both QPainter-based (for live preview) and numpy/OpenCV-based
(for export) keystroke rendering using the recorded key event data.
Displays keystrokes as floating badges or text with configurable position,
style, and duration.
"""

import bisect
import logging
from typing import List, Tuple

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
_KEYSTROKE_OPACITY_UNUSED = 0.9           # retained for back-compat; use config.opacity

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
    filter_mode: str = "shortcuts-only",
) -> List[Tuple[str, float, float]]:
    """Group recent keystrokes into display strings.
    
    Groups rapid successive keystrokes that occur within a short window
    into combo displays (e.g., "Ctrl+C" or "Alt+Tab").
    
    Uses binary search to limit scanning to events within the visible
    time window instead of iterating the full list.
    
    Args:
        key_events: All recorded key events (sorted by timestamp)
        timestamp_ms: Current playback time
        display_duration_ms: How long keystrokes remain visible
        filter_mode: "all", "modifiers-only", or "shortcuts-only"
        
    Returns:
        List of (display_text, timestamp, age) tuples for visible keystrokes
    """
    if not key_events:
        return []
    
    # Modifier key VK codes: Ctrl, Alt, Win (but not Shift alone)
    MODIFIER_VKS = frozenset((
        0x11,         # Ctrl
        0x12,         # Alt
        0xA2, 0xA3,   # LCtrl, RCtrl
        0xA4, 0xA5,   # LAlt, RAlt
        0x5B, 0x5C,   # LWin, RWin
    ))
    
    SHIFT_VKS = frozenset((0x10, 0xA0, 0xA1))  # Shift, LShift, RShift
    
    # Binary search for the visible time window to avoid scanning entire list
    window_start = timestamp_ms - display_duration_ms
    lo = bisect.bisect_left(
        key_events, window_start, key=lambda e: e.timestamp
    )
    hi = bisect.bisect_right(
        key_events, timestamp_ms, key=lambda e: e.timestamp
    )
    window_events = key_events[lo:hi]
    
    visible = []
    for event in window_events:
        age = timestamp_ms - event.timestamp
        if age < 0 or age > display_duration_ms:
            continue
        
        # Skip events without vk_code
        if not hasattr(event, 'vk_code') or event.vk_code is None:
            continue
        
        vk_code = event.vk_code
        key_name = _format_key_event(vk_code)
        
        # All events are kept for grouping; filtering happens at the
        # group level via _should_show_group so that combos like Ctrl+C
        # retain their non-modifier key in modifiers-only mode.
        
        visible.append((key_name, event.timestamp, age, vk_code))
    
    # Group keystrokes that are close together (within 100ms)
    if not visible:
        return []
    
    grouped = []
    current_group = [visible[0][0]]
    current_vks = [visible[0][3]]
    group_start = visible[0][1]
    
    for i in range(1, len(visible)):
        key_name, ts, _, vk_code = visible[i]
        if ts - visible[i-1][1] < 100:  # 100ms window for grouping
            current_group.append(key_name)
            current_vks.append(vk_code)
        else:
            # Finalize current group - apply filter
            if _should_show_group(current_vks, filter_mode, MODIFIER_VKS, SHIFT_VKS):
                group_age = timestamp_ms - group_start
                grouped.append(("+".join(current_group), group_start, group_age))
            current_group = [key_name]
            current_vks = [vk_code]
            group_start = ts
    
    # Don't forget the last group
    if current_group and _should_show_group(current_vks, filter_mode, MODIFIER_VKS, SHIFT_VKS):
        group_age = timestamp_ms - group_start
        grouped.append(("+".join(current_group), group_start, group_age))
    
    return grouped


def _should_show_group(
    vk_codes: List[int],
    filter_mode: str,
    modifier_vks: frozenset,
    shift_vks: frozenset,
) -> bool:
    """Determine if a keystroke group should be shown based on filter mode.
    
    Args:
        vk_codes: List of VK codes in this group
        filter_mode: "all", "modifiers-only", or "shortcuts-only"
        modifier_vks: Set of modifier VK codes (Ctrl, Alt, Win)
        shift_vks: Set of Shift VK codes
        
    Returns:
        True if the group should be displayed
    """
    if filter_mode == "all":
        return True
    
    # Prefer explicit modifier detection when the recording contains
    # Ctrl/Alt/Win key events.  Some recording paths only preserve the
    # resulting grouped keystrokes, though, so fall back to a
    # conservative multi-key heuristic instead of filtering everything.
    has_modifier = any(vk in modifier_vks for vk in vk_codes)
    has_shift = any(vk in shift_vks for vk in vk_codes)
    distinct_non_shift_vks = {vk for vk in vk_codes if vk not in shift_vks}
    has_multi_key_combo = len(distinct_non_shift_vks) > 1
    
    if filter_mode == "modifiers-only":
        # Show explicit Ctrl/Alt/Win combinations when available.  If
        # those modifier VKs were not recorded, still allow likely
        # modified combos through so this mode doesn't suppress
        # everything.  Shift-only typing is excluded.
        return has_modifier or has_multi_key_combo
    
    if filter_mode == "shortcuts-only":
        # Single Shift+letter is not considered a shortcut.  When
        # explicit modifier events are unavailable, treat only
        # non-Shift multi-key groups as shortcuts.
        if has_modifier:
            return True
        return has_multi_key_combo and not (
            has_shift and len(distinct_non_shift_vks) <= 1
        )
    
    # Unknown filter_mode — default to safe behavior (shortcuts-only)
    logger.warning("Unknown keystroke filter_mode %r, defaulting to shortcuts-only", filter_mode)
    if has_modifier:
        return True
    return has_multi_key_combo and not (
        has_shift and len(distinct_non_shift_vks) <= 1
    )


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
    
    grouped = _group_keystrokes(
        key_events, timestamp_ms, config.display_duration_ms, config.filter_mode
    )
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
        # Near-cursor placement: use the last key event's cursor position
        # if available; otherwise fall back to bottom-center.
        placed_near = False
        if key_events:
            # Find most recent event with cursor position
            for ev in reversed(key_events):
                if ev.timestamp <= timestamp_ms and ev.x is not None and ev.y is not None:
                    # Map screen coords to preview coords
                    if monitor_rect:
                        m_left = monitor_rect.get("left", 0)
                        m_top = monitor_rect.get("top", 0)
                        m_w = monitor_rect.get("width", 1)
                        m_h = monitor_rect.get("height", 1)
                        rel_x = (ev.x - m_left) / max(m_w, 1)
                        rel_y = (ev.y - m_top) / max(m_h, 1)
                        base_x = screen_rect_x + rel_x * screen_rect_w
                        base_y = screen_rect_y + rel_y * screen_rect_h - 50
                        placed_near = True
                    break
        if not placed_near:
            logger.debug("near-cursor position: no cursor data available, falling back to bottom-center")
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
    
    grouped = _group_keystrokes(
        key_events, timestamp_ms, config.display_duration_ms, config.filter_mode
    )
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
        # Near-cursor placement: use last key event's cursor position
        # if available; otherwise fall back to bottom-center.
        placed_near = False
        if key_events:
            for ev in reversed(key_events):
                if ev.timestamp <= timestamp_ms and ev.x is not None and ev.y is not None:
                    # Map screen coords to frame coords
                    rel_x = (ev.x - mon_left) / max(mon_w, 1)
                    rel_y = (ev.y - mon_top) / max(mon_h, 1)
                    base_x = int(rel_x * fw)
                    base_y = int(rel_y * fh) - 50
                    placed_near = True
                    break
        if not placed_near:
            logger.debug("near-cursor position: no cursor data, falling back to bottom-center")
            base_x = fw // 2
            base_y = fh - 60
    
    # Font settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = config.font_size / 18.0  # Base scale
    font_thickness = max(1, int(font_scale * 2))
    
    # Draw each visible keystroke group using a single overlay copy
    y_offset = 0
    overlay = None  # lazily allocated once per frame
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
        
        # Allocate a single overlay copy for the entire frame
        if overlay is None:
            overlay = frame_bgr.copy()
        
        # Draw badge background
        if config.style == "floating-badge":
            cv2.rectangle(
                overlay,
                (badge_x, badge_y),
                (badge_x + badge_w, badge_y + badge_h),
                KEYSTROKE_BG_COLOR_BGR,
                -1,
            )
        elif config.style == "key-cap":
            cv2.rectangle(
                overlay,
                (badge_x, badge_y),
                (badge_x + badge_w, badge_y + badge_h),
                KEYSTROKE_BG_COLOR_BGR,
                -1,
            )
            # Inner highlight
            highlight_h = badge_h // 3
            cv2.rectangle(
                overlay,
                (badge_x + 3, badge_y + 3),
                (badge_x + badge_w - 3, badge_y + highlight_h),
                (100, 90, 110),
                -1,
            )
        else:  # minimal-text
            cv2.rectangle(
                overlay,
                (badge_x, badge_y),
                (badge_x + badge_w, badge_y + badge_h),
                KEYSTROKE_BG_COLOR_BGR,
                -1,
            )
        
        # Blend badge region with frame using alpha
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
