"""Timeline widget — Clipchamp-inspired with playback controls, heatmap & keyframes."""

import math
from typing import List

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QLinearGradient,
    QFont,
    QMouseEvent,
    QWheelEvent,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu, QScrollBar

from ..models import ZoomKeyframe, MousePosition, KeyEvent, ClickEvent, VoiceoverSegment, VideoSegment, Chapter
from ..utils import fmt_time as _fmt
from .timeline_math import (
    trim_eff_start, trim_eff_end, trim_eff_dur, trim_ms_to_x, trim_x_to_ms,
    view_ms_to_x, view_x_to_ms, view_max_scale, view_clamp_offset,
)


def _fmt_precise(ms: float) -> str:
    total_s = ms / 1000
    m = int(total_s) // 60
    s = int(total_s) % 60
    cs = int((total_s - int(total_s)) * 100)
    return f"{m}:{s:02d}.{cs:02d}"


class _TimelineTrack(QWidget):
    """Custom-painted track showing activity heatmap, zoom segments, and trim handles.

    Handles hit-testing for segment edges (drag to resize), segment
    bodies (click to select, drag to move), click markers (right-click
    to delete), and trim handles at both ends.
    """
    """Custom-painted track showing heatmap, zoom segments, keyframes, and playhead."""

    clicked = Signal(float)  # absolute timestamp ms
    keyframe_moved = Signal(str, float)  # keyframe id, new timestamp (ms)
    segment_clicked = Signal(str, float) # (start kf id, click timestamp ms)
    segment_deleted = Signal(str)        # start keyframe id of segment to delete
    click_event_deleted = Signal(int)    # index of click event to delete
    pan_point_clicked = Signal(str, str) # (pan kf id, segment start kf id)
    add_zoom_requested = Signal(float)   # timestamp ms — add zoom at this time
    add_voiceover_requested = Signal(float)  # timestamp ms — add voiceover at this time
    voiceover_clicked = Signal(str)       # voiceover segment id — edit
    voiceover_deleted = Signal(str)       # voiceover segment id — delete directly
    voiceover_moved = Signal(str, float)  # voiceover segment id, new timestamp ms
    video_segment_deleted = Signal(str)  # video segment id — delete
    split_requested = Signal(float)       # timestamp ms — split recording here
    trim_changed = Signal(float, float)  # (trim_start_ms, trim_end_ms)
    trim_reset = Signal()                # reset both trim handles to full range
    drag_finished = Signal()             # emitted when any drag completes

    EDGE_GRAB_PX = 6  # pixel tolerance for grabbing a segment edge
    CLICK_HIT_PX = 8  # pixel tolerance for clicking on a click marker
    TRIM_GRAB_PX = 8  # pixel tolerance for grabbing a trim handle
    TRIM_SNAP_PX = 8  # pixel threshold for snapping trim handle to playhead
    MIN_VIEW_SCALE = 1.0  # 1.0 = fit-all (minimum zoom level)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setMaximumHeight(160)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_right_click)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self.duration: float = 0
        self.current_time: float = 0
        self.keyframes: List[ZoomKeyframe] = []
        self.mouse_track: List[MousePosition] = []
        self.key_events: List[KeyEvent] = []
        self.click_events: List[ClickEvent] = []
        self.voiceover_segments: List[VoiceoverSegment] = []
        self.video_segments: List[VideoSegment] = []
        self.trim_start_ms: float = 0.0
        self.trim_end_ms: float = 0.0  # 0 = no trim
        self.chapters: List[Chapter] = []

        # Trim handle drag state (relative drag using frozen anchor)
        self._drag_trim_start_x: float = 0.0
        self._drag_trim_initial_val: float = 0.0

        # Drag state for zoom segment resizing / moving
        self._drag_kf_id: str | None = None    # which keyframe is being dragged
        self._drag_edge_is_right: bool = False  # True when dragging right edge of segment
        self._dragging: bool = False
        self._drag_mode: str = ""              # "edge" | "body" | "trim_start" | "trim_end" | "pan_point"
        self._drag_body_ids: list = []          # [start_kf_id, end_kf_id] for body drag
        self._drag_body_offset: float = 0.0     # ms offset from click to segment start
        self._drag_body_seg_duration: float = 0  # original segment duration in ms
        self._drag_pan_seg_id: str = ""         # segment start id for pan point drag
        self._segments: List[tuple] = []       # [(start_x, end_x, start_kf_id, end_kf_id)]
        self._seg_top: int = 0
        self._seg_h: int = 0

        # Click event selection
        self._selected_click_idx: int = -1     # index into click_events, -1 = none
        self._click_top: int = 0               # y-offset for click track
        self._click_h: int = 0                 # height of click track

        # Pan point markers — populated during paintEvent for hit-testing
        # Each entry: (center_x, center_y, radius, kf_id, segment_start_id)
        self._pan_point_markers: List[tuple] = []

        # Zoom segment selection
        self._selected_segment_id: str = ""     # start kf id of selected segment
        # Video segment selection
        self._selected_video_seg_id: str = ""   # video segment id of selected segment
        # Video segment rendering cache — populated during paintEvent for hit-testing
        # Each entry: (x, width, segment_id)
        self._video_seg_rects: List[tuple] = []
        self._video_seg_top: int = 0
        self._video_seg_h: int = 0
        # Voiceover selection
        self._selected_vo_id: str = ""          # voiceover segment id
        # Track mouse press position to distinguish click from drag
        self._press_pos: QPointF | None = None
        self._drag_actually_moved: bool = False
        self._pending_select_id: str = ""       # segment to select on release if no drag
        # Trim-handle snap-to-playhead state
        self._trim_snapped: bool = False

        # View zoom/pan state
        self._view_scale: float = 1.0   # 1.0 = fit-all
        self._view_offset: float = 0.0  # left-edge offset in ms

    # ── trim-aware coordinate helpers ─────────────────────────────────

    @property
    def _eff_start(self) -> float:
        """Effective start of the visible timeline range (ms)."""
        return trim_eff_start(self.trim_start_ms)

    @property
    def _eff_end(self) -> float:
        """Effective end of the visible timeline range (ms)."""
        return trim_eff_end(self.trim_end_ms, self.duration)

    @property
    def _eff_dur(self) -> float:
        """Effective visible duration (ms)."""
        return trim_eff_dur(self.trim_start_ms, self.trim_end_ms, self.duration)

    _MENU_STYLE = (
        "QMenu { background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58;"
        "        border-radius: 6px; padding: 4px 0; }"
        "QMenu::item { padding: 6px 16px; }"
        "QMenu::item:selected { background: #8b5cf6; border-radius: 4px; margin: 0 4px; }"
        "QMenu::separator { height: 1px; background: #3d3a58; margin: 4px 8px; }"
    )

    # ── coordinate mapping helpers ────────────────────────────────

    def _ms_to_x(self, ms: float, _w: int | None = None) -> float:
        """Map a time in milliseconds to a widget x-coordinate, accounting for view zoom/pan."""
        return view_ms_to_x(ms, self.duration, self._view_scale, self._view_offset, self.width())

    def _x_to_ms(self, x: float, _w: int | None = None) -> float:
        """Map a widget x-coordinate to a time in milliseconds, accounting for view zoom/pan."""
        return view_x_to_ms(x, self.duration, self._view_scale, self._view_offset, self.width())

    def _max_view_scale(self) -> float:
        """Maximum view scale: 1 pixel = 10 ms."""
        return view_max_scale(self.duration, self.width())

    def _clamp_offset(self) -> None:
        """Clamp _view_offset so the viewport stays within [0, duration]."""
        self._view_offset = view_clamp_offset(self._view_offset, self.duration, self._view_scale)

    def _clamp_view(self) -> None:
        """Ensure view scale/offset are valid for the current duration and width."""
        self._view_scale = max(self.MIN_VIEW_SCALE, min(self._view_scale, self._max_view_scale()))
        self._clamp_offset()

    # ── public view API ────────────────────────────────────────────

    @property
    def view_scale(self) -> float:
        """Current time-axis zoom factor (1.0 = fit-all, read-only)."""
        return self._view_scale

    @property
    def view_offset(self) -> float:
        """Left-edge offset of the viewport in ms (read-only)."""
        return self._view_offset

    def set_view_offset(self, offset_ms: float) -> None:
        """Set the left-edge offset and clamp to valid range."""
        self._view_offset = offset_ms
        self._clamp_offset()
        self.update()

    def reset_view(self) -> None:
        """Reset zoom to fit-all (scale=1, offset=0)."""
        self._view_scale = 1.0
        self._view_offset = 0.0
        self.view_changed.emit()
        self.update()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        """Clamp view state when the widget is resized."""
        super().resizeEvent(event)
        self._clamp_view()
        self.view_changed.emit()

    # ── scroll-wheel zoom ─────────────────────────────────────────

    view_changed = Signal()  # emitted when view_scale or view_offset changes

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        """Scroll-wheel zooms the time axis, centered on the cursor position."""
        if self.duration <= 0:
            event.ignore()
            return

        degrees = event.angleDelta().y() / 8.0
        steps = degrees / 15.0  # standard mouse wheel: 1 step = 15°

        if steps == 0:
            event.ignore()
            return

        zoom_factor = 1.15 ** steps  # ~15% per wheel step
        old_scale = self._view_scale
        new_scale = old_scale * zoom_factor
        new_scale = max(self.MIN_VIEW_SCALE, min(new_scale, self._max_view_scale()))

        if new_scale == old_scale:
            event.accept()
            return

        # Keep the time under the cursor fixed
        cursor_ms = self._x_to_ms(event.position().x())
        self._view_scale = new_scale
        # Recompute offset so cursor_ms stays at the same x position
        visible_duration = self.duration / self._view_scale
        w = self.width()
        if w > 0:
            ratio = event.position().x() / w
            self._view_offset = cursor_ms - ratio * visible_duration
        self._clamp_offset()
        self.view_changed.emit()
        self.update()
        event.accept()

    def _on_right_click(self, pos) -> None:
        """Right-click on a pan point, zoom segment, click event, trim handle, or empty space."""
        mx, my = pos.x(), pos.y()
        # Check trim handle right-click — offer "Reset trim"
        trim_hit = self._trim_hit_test(mx)
        if trim_hit:
            is_trimmed = self.trim_start_ms > 0 or (
                self.trim_end_ms > 0 and self.trim_end_ms < self.duration
            )
            if is_trimmed:
                menu = QMenu(self)
                menu.setStyleSheet(self._MENU_STYLE)
                reset_act = menu.addAction("↩  Reset trim")
                reset_act.triggered.connect(self._reset_trim)
                menu.exec(self.mapToGlobal(pos))
            return
        # Check pan point markers first (higher priority than segment body)
        for cx, cy, r, pp_kf_id, seg_start_id in self._pan_point_markers:
            if (mx - cx) ** 2 + (my - cy) ** 2 <= (r + 3) ** 2:
                self.pan_point_clicked.emit(pp_kf_id, seg_start_id)
                return
        # Check zoom segment
        seg_info = self._segment_body_hit_info(mx, my)
        if seg_info:
            start_id, end_id, sx, ex = seg_info
            # Compute the click timestamp from x position
            click_time_ms = 0.0
            if self._eff_dur > 0 and self.width() > 0:
                click_time_ms = self._x_to_ms(max(0.0, min(float(mx), float(self.width()))), self.width())
            self.segment_clicked.emit(start_id, click_time_ms)
            return
        # Check click event marker
        click_idx = self._click_hit_test(mx, my)
        if click_idx >= 0:
            self._selected_click_idx = click_idx
            self.update()
            menu = QMenu(self)
            menu.setStyleSheet(self._MENU_STYLE)
            del_act = menu.addAction("🗑  Delete click event")
            del_act.triggered.connect(lambda: self._delete_selected_click())
            menu.exec(self.mapToGlobal(pos))
            return
        # Check voiceover segment
        vo_id = self._voiceover_hit_test(mx, my)
        if vo_id:
            self._selected_vo_id = vo_id
            self.update()
            menu = QMenu(self)
            menu.setStyleSheet(self._MENU_STYLE)
            edit_act = menu.addAction("✏  Edit voiceover")
            edit_act.triggered.connect(lambda: self.voiceover_clicked.emit(vo_id))
            del_act = menu.addAction("🗑  Delete voiceover")
            del_act.triggered.connect(lambda: self._delete_selected_voiceover())
            menu.exec(self.mapToGlobal(pos))
            return
        # Check video segment
        vs_id = self._video_seg_hit_test(mx, my)
        if vs_id:
            # Selecting a video segment should clear all other selection state
            self._selected_segment_id = ""
            self._selected_click_idx = -1
            self._selected_vo_id = ""
            self._selected_video_seg_id = vs_id
            self.update()
            # Only show delete if more than 1 segment remains
            if len(self.video_segments) > 1:
                menu = QMenu(self)
                menu.setStyleSheet(self._MENU_STYLE)
                del_act = menu.addAction("🗑  Delete segment")
                del_act.triggered.connect(lambda: self._delete_selected_video_segment())
                menu.exec(self.mapToGlobal(pos))
            return
        # Empty space — offer to add a zoom section, voiceover, or split
        if self._eff_dur > 0 and self.width() > 0:
            time_ms = self._x_to_ms(max(0.0, min(float(mx), float(self.width()))), self.width())
            menu = QMenu(self)
            menu.setStyleSheet(self._MENU_STYLE)
            act_split = menu.addAction("✂  Split here")
            act_split.triggered.connect(
                lambda: self.split_requested.emit(self.current_time)
            )
            menu.addSeparator()
            act_zoom = menu.addAction("🔍  Add Zoom here")
            act_zoom.triggered.connect(
                lambda: self.add_zoom_requested.emit(time_ms)
            )
            act_vo = menu.addAction("🎙  Add Voiceover here")
            act_vo.triggered.connect(
                lambda: self.add_voiceover_requested.emit(time_ms)
            )
            menu.exec(self.mapToGlobal(pos))

    # ── painting ────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # background
        painter.fillRect(0, 0, w, h, QColor("#1b1a2e"))

        # track bg (rounded)
        painter.setBrush(QBrush(QColor("#201f34")))
        painter.setPen(QPen(QColor("#2d2b45"), 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 6, 6)

        if self.duration <= 0:
            painter.end()
            return

        # time markers along top
        self._draw_time_markers(painter, w)

        # Activity tracks: Mouse (20px), Keyboard (14px), Clicks (14px)
        mouse_top = 16
        mouse_h = 20
        self._draw_mouse_track(painter, w, mouse_top, mouse_h)

        keyboard_top = mouse_top + mouse_h + 2
        keyboard_h = 14
        self._draw_keyboard_track(painter, w, keyboard_top, keyboard_h)

        self._click_top = keyboard_top + keyboard_h + 2
        self._click_h = 14
        self._draw_click_track(painter, w, self._click_top, self._click_h)

        # zoom segment blocks (below activity tracks)
        self._seg_top = self._click_top + self._click_h + 4
        self._seg_h = 28
        self._draw_zoom_segments(painter, w, self._seg_top, self._seg_h)

        # voiceover segments (below zoom segments)
        self._vo_top = self._seg_top + self._seg_h + 2
        self._vo_h = 18
        self._draw_voiceover_segments(painter, w, self._vo_top, self._vo_h)

        # video segments (below voiceover, only when multiple segments exist)
        if len(self.video_segments) > 1:
            self._video_seg_top = self._vo_top + self._vo_h + 2
            self._video_seg_h = 18
            self._draw_video_segments(painter, w, self._video_seg_top, self._video_seg_h)
        else:
            self._video_seg_rects = []

        # chapter markers (small flags along the bottom)
        if self.chapters:
            self._draw_chapter_markers(painter, w, h)

        # playhead
        px = self._ms_to_x(self.current_time, w)
        playhead_color = QColor("#facc15") if self._trim_snapped else QColor("#ffffff")
        painter.setPen(QPen(playhead_color, 2))
        painter.drawLine(int(px), 0, int(px), h)
        # playhead handle
        painter.setBrush(QBrush(playhead_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(px, 0), 5, 5)

        # ── Trim handles ───────────────────────────────────────────
        self._draw_trim_handles(painter, w, h)

        painter.end()

    def _draw_time_markers(self, painter: QPainter, w: int) -> None:
        eff_dur = self._eff_dur
        if eff_dur <= 0:
            return
        # draw tick marks at intervals based on visible duration
        interval_ms = 5000
        if eff_dur < 30000:
            interval_ms = 5000
        elif eff_dur < 120000:
            interval_ms = 10000
        else:                             # ≥2 min visible → 30 s ticks
            interval_ms = 30000

        font = QFont()
        font.setFamily("Segoe UI Variable")
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#5a5873"), 1))

        eff_start = self._eff_start
        eff_end = self._eff_end
        t = eff_start
        while t <= eff_end:
            x = self._ms_to_x(t, w)
            painter.drawLine(int(x), 0, int(x), 4)
            display_t = t - eff_start  # re-index to 0:00
            if display_t > 0 and x < w - 30:
                painter.drawText(int(x) + 2, 12, _fmt(display_t))
            t += interval_ms

    def _draw_mouse_track(self, painter: QPainter, w: int, top: int, h: int) -> None:
        """Draw mouse speed heatmap — purple gradient."""
        track = self.mouse_track
        eff_dur = self._eff_dur
        if len(track) < 2 or eff_dur <= 0:
            return

        # Track label
        label_font = QFont()
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        painter.setPen(QPen(QColor("#6c6890"), 1))
        painter.drawText(4, top + h - 3, "Mouse")

        eff_start = self._eff_start
        eff_end = self._eff_end
        buckets = max(1, min(w, 200))
        speeds = [0.0] * buckets
        max_speed = 0.0

        for i in range(1, len(track)):
            prev, curr = track[i - 1], track[i]
            # Filter to trimmed range
            if curr.timestamp < eff_start or curr.timestamp > eff_end:
                continue
            dx = curr.x - prev.x
            dy = curr.y - prev.y
            dt = max(curr.timestamp - prev.timestamp, 1)
            speed = math.sqrt(dx * dx + dy * dy) / dt
            bucket = min(buckets - 1, max(0, int(((curr.timestamp - eff_start) / eff_dur) * buckets)))
            speeds[bucket] = max(speeds[bucket], speed)
            max_speed = max(max_speed, speed)

        if max_speed == 0:
            return

        bw = w / buckets
        for i, s in enumerate(speeds):
            intensity = s / max_speed
            r = int(120 + intensity * 100)
            g = int(60 + intensity * 20)
            b = int(220 + intensity * 35)
            a = int((0.3 + intensity * 0.6) * 255)
            painter.fillRect(QRectF(i * bw, top, bw + 1, h), QColor(r, g, b, a))

    def _draw_keyboard_track(self, painter: QPainter, w: int, top: int, h: int) -> None:
        """Draw keyboard activity — cyan bars for keystroke density."""
        eff_dur = self._eff_dur
        events = self.key_events
        if not events or eff_dur <= 0:
            return

        # Track label
        label_font = QFont()
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        painter.setPen(QPen(QColor("#6c6890"), 1))
        painter.drawText(4, top + h - 2, "Keys")

        eff_start = self._eff_start
        eff_end = self._eff_end
        buckets = max(1, min(w, 200))
        counts = [0] * buckets
        max_count = 0

        for ev in events:
            if ev.timestamp < eff_start or ev.timestamp > eff_end:
                continue
            bucket = min(buckets - 1, max(0, int(((ev.timestamp - eff_start) / eff_dur) * buckets)))
            counts[bucket] += 1
            max_count = max(max_count, counts[bucket])

        if max_count == 0:
            return

        bw = w / buckets
        for i, c in enumerate(counts):
            if c == 0:
                continue
            intensity = c / max_count
            # Cyan/teal palette
            r = int(20 + intensity * 40)
            g = int(180 + intensity * 75)
            b = int(200 + intensity * 55)
            a = int((0.35 + intensity * 0.55) * 255)
            painter.fillRect(QRectF(i * bw, top, bw + 1, h), QColor(r, g, b, a))

    def _draw_click_track(self, painter: QPainter, w: int, top: int, h: int) -> None:
        """Draw click events — orange markers, selected click highlighted."""
        events = self.click_events
        if not events or self._eff_dur <= 0:
            return

        # Track label
        label_font = QFont()
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        painter.setPen(QPen(QColor("#6c6890"), 1))
        painter.drawText(4, top + h - 2, "Clicks")

        eff_start = self._eff_start
        eff_end = self._eff_end
        mid_y = top + h / 2.0
        for i, ev in enumerate(events):
            if ev.timestamp < eff_start or ev.timestamp > eff_end:
                continue
            x = self._ms_to_x(ev.timestamp, w)
            if i == self._selected_click_idx:
                # Selected: larger, brighter, with outline
                painter.setPen(QPen(QColor(255, 255, 255), 1.5))
                painter.setBrush(QBrush(QColor(255, 100, 30, 255)))
                painter.drawEllipse(QPointF(x, mid_y), 5, 5)
            else:
                marker_color = QColor(255, 160, 50, 200)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(marker_color))
                painter.drawEllipse(QPointF(x, mid_y), 3, 3)

    def _draw_zoom_segments(self, painter: QPainter, w: int, top: int, h: int) -> None:
        """Draw rounded-rect zoom segment blocks with internal zoom-in/out markers."""
        self._segments = []
        self._pan_point_markers = []

        # Always draw track label
        label_font = QFont()
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        painter.setPen(QPen(QColor("#6c6890"), 1))
        painter.drawText(4, top + h - 3, "Zoom")

        if not self.keyframes or self._eff_dur <= 0:
            return

        # Build segments directly from keyframe pairs instead of sampling
        # to avoid precision issues where close blocks merge visually.
        eff_start = self._eff_start
        eff_end = self._eff_end
        sorted_kfs = sorted(self.keyframes, key=lambda k: k.timestamp)
        i = 0
        while i < len(sorted_kfs):
            kf = sorted_kfs[i]
            if kf.zoom > 1.01:  # zoom-in → start of a block
                start_ms = kf.timestamp
                start_id = kf.id
                # Walk forward past any pans (zoom > 1.01) to the zoom-out
                j = i + 1
                while j < len(sorted_kfs) and sorted_kfs[j].zoom > 1.01:
                    j += 1
                if j < len(sorted_kfs) and sorted_kfs[j].zoom <= 1.01:
                    end_kf = sorted_kfs[j]
                    end_ms = min(end_kf.timestamp + end_kf.duration, self.duration)
                    end_id = end_kf.id
                    i = j + 1
                else:
                    # No zoom-out found — block extends to end of video
                    end_ms = self.duration
                    end_id = ""
                    i = len(sorted_kfs)
                # Skip segments entirely outside the trimmed range
                if end_ms < eff_start or start_ms > eff_end:
                    continue
                sx = self._ms_to_x(start_ms, w)
                ex = self._ms_to_x(end_ms, w)
                if ex - sx > 4:
                    self._segments.append((sx, ex, start_id, end_id))
            else:
                i += 1

        # Draw each zoom segment
        font = QFont()
        font.setFamily("Segoe UI Variable")
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)

        for sx, ex, start_id, end_id in self._segments:
            seg_w = ex - sx
            rect = QRectF(sx, top, seg_w, h)

            is_selected = (start_id and start_id == self._selected_segment_id)

            # Background fill — brighter when selected
            if is_selected:
                painter.setBrush(QBrush(QColor(139, 92, 246, 80)))
                painter.setPen(QPen(QColor("#a78bfa"), 2.0))
            else:
                painter.setBrush(QBrush(QColor(139, 92, 246, 40)))
                painter.setPen(QPen(QColor("#8b5cf6"), 1.5))
            painter.drawRoundedRect(rect, 4, 4)

            # Find the zoom-in and zoom-out keyframes for markers
            kf_in = next((kf for kf in sorted_kfs if kf.id == start_id), None)
            kf_out = next((kf for kf in sorted_kfs if kf.id == end_id), None)

            # ── Internal transition markers ──
            # Zoom-in marker: where the zoom-in transition completes
            if kf_in and self._eff_dur > 0:
                kf_in_x = self._ms_to_x(kf_in.timestamp, w)
                # End of zoom-in transition
                kf_in_end_x = self._ms_to_x(kf_in.timestamp + kf_in.duration, w)
                # Draw zoom-in ramp (lighter fill for the transition region)
                ramp_left = max(sx, kf_in_x)
                ramp_right = min(ex, kf_in_end_x)
                if ramp_right > ramp_left + 2:
                    grad_in = QLinearGradient(ramp_left, 0, ramp_right, 0)
                    grad_in.setColorAt(0.0, QColor(139, 92, 246, 15))
                    grad_in.setColorAt(1.0, QColor(139, 92, 246, 70))
                    painter.setBrush(QBrush(grad_in))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(QRectF(ramp_left, top + 1, ramp_right - ramp_left, h - 2))

                    # Small triangle pointing right at the transition end
                    tri_x = ramp_right
                    tri_y = top + h / 2
                    tri_size = min(5, h / 4)
                    painter.setBrush(QBrush(QColor("#a78bfa")))
                    painter.drawConvexPolygon([
                        QPointF(tri_x - tri_size, tri_y - tri_size),
                        QPointF(tri_x, tri_y),
                        QPointF(tri_x - tri_size, tri_y + tri_size),
                    ])

            # Zoom-out marker: where the zoom-out transition begins
            if kf_out and self._eff_dur > 0:
                kf_out_x = self._ms_to_x(kf_out.timestamp, w)
                kf_out_end_x = self._ms_to_x(kf_out.timestamp + kf_out.duration, w)
                # Draw zoom-out ramp (lighter fill fading out)
                ramp_left = max(sx, kf_out_x)
                ramp_right = min(ex, kf_out_end_x)
                if ramp_right > ramp_left + 2:
                    grad_out = QLinearGradient(ramp_left, 0, ramp_right, 0)
                    grad_out.setColorAt(0.0, QColor(139, 92, 246, 70))
                    grad_out.setColorAt(1.0, QColor(139, 92, 246, 15))
                    painter.setBrush(QBrush(grad_out))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(QRectF(ramp_left, top + 1, ramp_right - ramp_left, h - 2))

                    # Small triangle pointing left at the transition start
                    tri_x = ramp_left
                    tri_y = top + h / 2
                    tri_size = min(5, h / 4)
                    painter.setBrush(QBrush(QColor("#facc15")))
                    painter.drawConvexPolygon([
                        QPointF(tri_x + tri_size, tri_y - tri_size),
                        QPointF(tri_x, tri_y),
                        QPointF(tri_x + tri_size, tri_y + tri_size),
                    ])

            # "🔍 Zoom" label — positioned in the steady-state region
            label_left = sx + 6
            if kf_in and self._eff_dur > 0:
                label_left = max(label_left, self._ms_to_x(kf_in.timestamp + kf_in.duration, w) + 4)
            label_right = ex - 6
            if kf_out and self._eff_dur > 0:
                label_right = min(label_right, self._ms_to_x(kf_out.timestamp, w) - 4)
            label_w = label_right - label_left
            if label_w > 40:
                painter.setPen(QPen(QColor("#a78bfa")))
                text_rect = QRectF(label_left, top, label_w, h)
                # Show speed badge if non-default speed is set on the zoom-in kf
                seg_speed = kf_in.speed if kf_in else 1.0
                if abs(seg_speed - 1.0) > 0.01:
                    speed_str = f"{seg_speed:.2f}".rstrip("0").rstrip(".")
                    speed_label = f"🔍 {speed_str}×"
                else:
                    speed_label = "🔍 Zoom"
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, speed_label)

            # ── Pan point markers (numbered circles for intermediate kfs) ──
            pan_points = []
            if kf_in and self._eff_dur > 0:
                for pp_kf in sorted_kfs:
                    if (pp_kf.id != start_id
                        and pp_kf.zoom > 1.01
                        and pp_kf.timestamp > kf_in.timestamp
                        and (kf_out is None or pp_kf.timestamp < kf_out.timestamp)):
                        pp_x = self._ms_to_x(pp_kf.timestamp, w)
                        pan_points.append((pp_x, pp_kf))

            if pan_points:
                # Draw connecting line through all pan points
                pan_line_y = top + h / 2
                painter.setPen(QPen(QColor("#facc15"), 1.5, Qt.PenStyle.DashLine))
                all_xs = [pan_points[0][0]] + [p[0] for p in pan_points]
                for idx in range(len(all_xs) - 1):
                    painter.drawLine(QPointF(all_xs[idx], pan_line_y),
                                     QPointF(all_xs[idx + 1], pan_line_y))

                # Draw numbered circle markers
                pp_font = QFont()
                pp_font.setFamily("Segoe UI Variable")
                pp_font.setPixelSize(9)
                pp_font.setWeight(QFont.Weight.Bold)
                painter.setFont(pp_font)
                for pp_idx, (pp_x, pp_kf) in enumerate(pan_points, start=1):
                    radius = 7
                    cy = top + h / 2
                    # Record for hit-testing
                    self._pan_point_markers.append((pp_x, cy, radius, pp_kf.id, start_id))
                    # Circle background
                    painter.setPen(QPen(QColor("#1b1a2e"), 1.5))
                    painter.setBrush(QBrush(QColor("#facc15")))
                    painter.drawEllipse(QPointF(pp_x, cy), radius, radius)
                    # Number label
                    painter.setPen(QPen(QColor("#1b1a2e")))
                    num_rect = QRectF(pp_x - radius, cy - radius, radius * 2, radius * 2)
                    painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, str(pp_idx))
                # Restore font
                painter.setFont(font)

            # Draw edge handles (vertical bars at edges)
            handle_color = QColor("#c4b5fd") if not self._dragging else QColor("#e9d5ff")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(handle_color))
            handle_w = 3
            # Left handle
            painter.drawRoundedRect(QRectF(sx, top + 2, handle_w, h - 4), 1, 1)
            # Right handle
            painter.drawRoundedRect(QRectF(ex - handle_w, top + 2, handle_w, h - 4), 1, 1)

    # ── voiceover segments ──────────────────────────────────────────

    def _draw_voiceover_segments(self, painter: QPainter, w: int, top: int, h: int) -> None:
        """Draw voiceover segments as teal pill-shaped blocks with text labels."""
        eff_dur = self._eff_dur
        self._vo_rects: list[tuple] = []  # [(x, w, seg_id)] for hit testing

        # Always draw track label
        label_font = QFont()
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        painter.setPen(QPen(QColor("#6c6890"), 1))
        painter.drawText(4, top + h - 3, "Voice")

        if eff_dur <= 0 or not self.voiceover_segments:
            return

        seg_font = QFont()
        seg_font.setFamily("Segoe UI Variable")
        seg_font.setPixelSize(10)

        eff_start = self._eff_start
        eff_end = self._eff_end

        for seg in self.voiceover_segments:
            # Filter voiceover segments outside the trimmed range
            seg_end = seg.timestamp + (seg.duration_ms if seg.duration_ms > 0 else 40)
            if seg_end < eff_start or seg.timestamp > eff_end:
                continue
            sx = self._ms_to_x(seg.timestamp, w)
            # Use audio duration if known, otherwise show a fixed-width marker
            if seg.duration_ms > 0:
                seg_w = max(20, self._ms_to_x(seg.timestamp + seg.duration_ms, w) - sx)
            else:
                seg_w = max(20, 40)  # minimum visible width

            # Segment fill — highlight selected
            is_selected = (seg.id == self._selected_vo_id)
            if is_selected:
                color = QColor("#14b8a6")
                border_color = QColor("#5eead4")
            elif seg.audio_path:
                color = QColor("#0d9488")
                border_color = QColor("#14b8a6")
            else:
                color = QColor("#475569")
                border_color = QColor("#64748b")
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(border_color, 2 if is_selected else 1))
            painter.drawRoundedRect(QRectF(sx, top, seg_w, h), 4, 4)

            # Text label (truncated)
            painter.setFont(seg_font)
            painter.setPen(QPen(QColor("#e2e8f0"), 1))
            text = seg.text[:20] + ("\u2026" if len(seg.text) > 20 else "")
            clip_rect = QRectF(sx + 3, top + 1, seg_w - 6, h - 2)
            painter.drawText(clip_rect, Qt.AlignmentFlag.AlignVCenter, text)

            # Mic icon if no audio yet
            if not seg.audio_path:
                painter.setPen(QPen(QColor("#94a3b8"), 1))
                painter.drawText(int(sx + seg_w - 12), top + h - 3, "\u2026")

            self._vo_rects.append((sx, seg_w, seg.id))

    def _voiceover_hit_test(self, mx: float, my: float) -> str:
        """Return the voiceover segment id at (mx, my), or empty string."""
        if not hasattr(self, "_vo_rects") or not hasattr(self, "_vo_top"):
            return ""
        if my < self._vo_top or my > self._vo_top + self._vo_h:
            return ""
        for sx, sw, seg_id in self._vo_rects:
            if sx <= mx <= sx + sw:
                return seg_id
        return ""

    # ── video segments ─────────────────────────────────────────────

    def _draw_video_segments(self, painter: QPainter, w: int, top: int, h: int) -> None:
        """Draw video segment blocks — teal rounded rects when multiple segments exist."""
        self._video_seg_rects = []
        if self.duration <= 0 or len(self.video_segments) <= 1:
            return

        # Track label
        label_font = QFont()
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        painter.setPen(QPen(QColor("#6c6890"), 1))
        painter.drawText(4, top + h - 3, "Clips")

        for seg in self.video_segments:
            sx = self._ms_to_x(seg.start_ms)
            ex = self._ms_to_x(seg.end_ms)
            seg_w = max(ex - sx, 4)
            rect = QRectF(sx, top, seg_w, h)

            is_selected = (seg.id == self._selected_video_seg_id)
            if is_selected:
                painter.setBrush(QBrush(QColor(34, 197, 168, 90)))
                painter.setPen(QPen(QColor("#2dd4bf"), 2.0))
            else:
                painter.setBrush(QBrush(QColor(34, 197, 168, 45)))
                painter.setPen(QPen(QColor("#14b8a6"), 1.0))
            painter.drawRoundedRect(rect, 3, 3)
            self._video_seg_rects.append((sx, seg_w, seg.id))

    def _video_seg_hit_test(self, mx: float, my: float) -> str:
        """Return the video segment id at (mx, my), or empty string."""
        if not self._video_seg_rects:
            return ""
        if my < self._video_seg_top or my > self._video_seg_top + self._video_seg_h:
            return ""
        for sx, sw, seg_id in self._video_seg_rects:
            if sx <= mx <= sx + sw:
                return seg_id
        return ""

    def _draw_chapter_markers(self, painter: QPainter, w: int, h: int) -> None:
        """Draw chapter markers as small flag icons along the bottom edge."""
        if self.duration <= 0 or not self.chapters:
            return

        marker_h = 16
        marker_y = h - marker_h - 2

        font = QFont()
        font.setFamily("Segoe UI Variable")
        font.setPixelSize(9)
        painter.setFont(font)

        for chapter in self.chapters:
            x = self._ms_to_x(chapter.timestamp_ms, w)
            if x < 0 or x > w:
                continue

            # Draw flag pole (vertical line)
            painter.setPen(QPen(QColor("#facc15"), 2))
            painter.drawLine(int(x), marker_y, int(x), marker_y + marker_h)

            # Draw flag (small triangle)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#facc15")))
            flag_w = 8
            flag_h = 6
            flag = QPolygonF([
                QPointF(x, marker_y),
                QPointF(x + flag_w, marker_y + flag_h / 2),
                QPointF(x, marker_y + flag_h),
            ])
            painter.drawPolygon(flag)

    # ── trim handles ──────────────────────────────────────────────

    def _draw_trim_handles(self, painter: QPainter, w: int, h: int) -> None:
        """Draw trim handle bars at the timeline edges.

        In trimmed view, the entire viewport shows only the content
        between trim_start and trim_end.  Handles sit at x=0 (left)
        and x=w (right) so the user can still drag to adjust.
        """
        if self.duration <= 0:
            return

        # Handle bars — always at the edges of the visible viewport
        handle_w = 4
        handle_color = QColor("#facc15")  # yellow accent
        snap_color = QColor("#ffffff")    # white highlight when snapped to playhead
        snapped_start = self._trim_snapped and self._drag_mode == "trim_start"
        snapped_end = self._trim_snapped and self._drag_mode == "trim_end"
        painter.setPen(Qt.PenStyle.NoPen)

        # Left (start) trim handle — always at x=0
        sx = 0
        painter.setBrush(QBrush(snap_color if snapped_start else handle_color))
        painter.drawRoundedRect(QRectF(sx, 0, handle_w, h), 2, 2)
        painter.setPen(QPen(QColor("#1b1a2e"), 1.5))
        mid_y = h / 2
        painter.drawLine(int(sx) + 1, int(mid_y) - 6, int(sx) + 1, int(mid_y) + 6)
        painter.drawLine(int(sx) + 3, int(mid_y) - 6, int(sx) + 3, int(mid_y) + 6)
        painter.setPen(Qt.PenStyle.NoPen)

        # Right (end) trim handle — always at x=w
        ex = w
        painter.setBrush(QBrush(snap_color if snapped_end else handle_color))
        painter.drawRoundedRect(QRectF(ex - handle_w, 0, handle_w, h), 2, 2)
        painter.setPen(QPen(QColor("#1b1a2e"), 1.5))
        painter.drawLine(int(ex) - 3, int(mid_y) - 6, int(ex) - 3, int(mid_y) + 6)
        painter.drawLine(int(ex) - 1, int(mid_y) - 6, int(ex) - 1, int(mid_y) + 6)
        painter.setPen(Qt.PenStyle.NoPen)

    def _trim_hit_test(self, x: float) -> str:
        """Check if x is over a trim handle. Returns 'trim_start', 'trim_end', or ''."""
        if self.duration <= 0:
            return ""
        w = self.width()
        grab = self.TRIM_GRAB_PX

        # Left handle is always at x=0 in the trimmed viewport
        if x <= grab:
            return "trim_start"
        # Right handle is always at x=w in the trimmed viewport
        if x >= w - grab:
            return "trim_end"
        return ""

    # ── mouse events ────────────────────────────────────────────────

    def _edge_hit_test(self, x: float, y: float) -> tuple | None:
        """Check if the mouse is over a segment edge handle.
        Returns (keyframe_id, is_right_edge) or None."""
        if y < self._seg_top or y > self._seg_top + self._seg_h:
            return None
        grab = self.EDGE_GRAB_PX
        for sx, ex, start_id, end_id in self._segments:
            if abs(x - sx) <= grab and start_id:
                return (start_id, False)
            if abs(x - ex) <= grab and end_id:
                return (end_id, True)
        return None

    def _segment_body_hit_info(self, x: float, y: float) -> tuple | None:
        """Check if the mouse is inside a zoom segment body (not on an edge).
        Returns (start_kf_id, end_kf_id, sx, ex) or None."""
        if y < self._seg_top or y > self._seg_top + self._seg_h:
            return None
        grab = self.EDGE_GRAB_PX
        for sx, ex, start_id, end_id in self._segments:
            # Inside the segment but not on an edge handle
            if sx + grab < x < ex - grab and start_id:
                return (start_id, end_id, sx, ex)
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.width() > 0:
            mx = event.position().x()
            my = event.position().y()
            # Check pan point marker drag first (highest priority)
            for cx, cy, r, pp_kf_id, seg_start_id in self._pan_point_markers:
                if (mx - cx) ** 2 + (my - cy) ** 2 <= (r + 3) ** 2:
                    self._dragging = True
                    self._drag_mode = "pan_point"
                    self._drag_kf_id = pp_kf_id
                    self._drag_pan_seg_id = seg_start_id
                    self._selected_click_idx = -1
                    self._selected_segment_id = ""
                    return
            # Check zoom segment edge drag first — takes priority over trim handles so
            # that blocks touching the video boundaries (x=0 or x=width) remain resizable.
            edge_hit = self._edge_hit_test(mx, my)
            if edge_hit:
                kf_id, is_right = edge_hit
                self._dragging = True
                self._drag_mode = "edge"
                self._drag_kf_id = kf_id
                self._drag_edge_is_right = is_right
                self._selected_click_idx = -1
                self._selected_segment_id = ""
                self._selected_video_seg_id = ""
                return
            # Check segment body drag (move entire segment)
            seg_info = self._segment_body_hit_info(mx, my)
            if seg_info:
                start_id, end_id, sx, ex = seg_info
                click_ms = self._x_to_ms(mx, self.width())
                # Use actual keyframe timestamps (not visual segment extent)
                # to prevent the segment from growing on each drag cycle.
                start_kf = next((k for k in self.keyframes if k.id == start_id), None)
                end_kf = next((k for k in self.keyframes if k.id == end_id), None) if end_id else None
                if start_kf:
                    kf_start_ms = start_kf.timestamp
                    kf_end_ms = end_kf.timestamp if end_kf else kf_start_ms
                else:
                    kf_start_ms = self._x_to_ms(sx, self.width())
                    kf_end_ms = self._x_to_ms(ex, self.width())
                self._dragging = True
                self._drag_mode = "body"
                self._drag_body_ids = [start_id, end_id]
                self._drag_body_offset = click_ms - kf_start_ms
                self._drag_body_seg_duration = kf_end_ms - kf_start_ms
                self._selected_click_idx = -1
                # Remember this segment for selection on release (if user
                # just clicks without dragging).
                self._pending_select_id = start_id
                self._drag_actually_moved = False
                self._press_pos = event.position()
                return
            # Check trim handle drag (after zoom blocks so handles at the video
            # boundaries don't steal clicks from zoom blocks touching those edges).
            trim_hit = self._trim_hit_test(mx)
            if trim_hit:
                self._dragging = True
                self._drag_mode = trim_hit
                self._drag_trim_start_x = mx
                if trim_hit == "trim_start":
                    self._drag_trim_initial_val = self.trim_start_ms
                else:
                    self._drag_trim_initial_val = self.trim_end_ms if self.trim_end_ms > 0 else self.duration
                self._selected_click_idx = -1
                self._selected_segment_id = ""
                self._selected_video_seg_id = ""
                return
            # Check click event selection
            click_idx = self._click_hit_test(mx, my)
            if click_idx >= 0:
                self._selected_click_idx = click_idx
                self._selected_segment_id = ""
                self._selected_vo_id = ""
                self._selected_video_seg_id = ""
                self.update()
                return
            # Check voiceover segment selection (left-click) — start drag
            vo_id = self._voiceover_hit_test(mx, my)
            if vo_id:
                self._selected_vo_id = vo_id
                self._selected_click_idx = -1
                self._selected_segment_id = ""
                self._selected_video_seg_id = ""
                # Start voiceover drag
                self._dragging = True
                self._drag_mode = "voiceover"
                self._drag_kf_id = vo_id
                click_ms = self._x_to_ms(mx, self.width())
                seg = next((s for s in self.voiceover_segments if s.id == vo_id), None)
                self._drag_body_offset = click_ms - seg.timestamp if seg else 0.0
                self._press_pos = event.position()
                self._drag_actually_moved = False
                self.update()
                return
            # Check video segment selection (left-click)
            vs_id = self._video_seg_hit_test(mx, my)
            if vs_id:
                self._selected_video_seg_id = vs_id
                self._selected_click_idx = -1
                self._selected_segment_id = ""
                self._selected_vo_id = ""
                self.update()
                return
            # Regular click — seek (and deselect any click/segment/voiceover)
            self._selected_click_idx = -1
            self._selected_segment_id = ""
            self._selected_vo_id = ""
            self._selected_video_seg_id = ""
            if self.duration > 0:
                click_time_ms = self._x_to_ms(mx)
                click_time_ms = max(0.0, min(click_time_ms, self.duration))
            else:
                click_time_ms = 0.0
            self.clicked.emit(click_time_ms)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        mx = event.position().x()
        my = event.position().y()

        if self._dragging and self.duration > 0:
            # Snap-to-playhead helper (only for trim handle drags): check
            # whether mx is close enough to the playhead and Alt is not held.
            snap_active = False
            if self._drag_mode in ("trim_start", "trim_end"):
                alt_held = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
                playhead_px = (self.current_time / self.duration) * self.width()
                snap_active = (
                    not alt_held
                    and abs(mx - playhead_px) <= self.TRIM_SNAP_PX
                )

            if self._drag_mode == "trim_start":
                if self.width() <= 0:
                    return
                if snap_active:
                    new_time = self.current_time
                    self._trim_snapped = True
                else:
                    # Relative drag: map pixel delta to time delta using full duration
                    delta_px = mx - self._drag_trim_start_x
                    delta_ms = (delta_px / self.width()) * self.duration
                    new_time = self._drag_trim_initial_val + delta_ms
                    self._trim_snapped = False
                trim_e = self.trim_end_ms if self.trim_end_ms > 0 else self.duration
                new_time = min(new_time, trim_e - 500)  # keep at least 500ms
                self.trim_start_ms = max(0.0, new_time)
                self.trim_changed.emit(self.trim_start_ms, self.trim_end_ms)
                self.update()
                return
            elif self._drag_mode == "trim_end":
                if self.width() <= 0:
                    return
                if snap_active:
                    new_time = self.current_time
                    self._trim_snapped = True
                else:
                    delta_px = mx - self._drag_trim_start_x
                    delta_ms = (delta_px / self.width()) * self.duration
                    new_time = self._drag_trim_initial_val + delta_ms
                    self._trim_snapped = False
                new_time = max(new_time, self.trim_start_ms + 500)
                self.trim_end_ms = min(self.duration, new_time)
                self.trim_changed.emit(self.trim_start_ms, self.trim_end_ms)
                self.update()
                return
            elif self._drag_mode == "edge" and self._drag_kf_id:
                new_time = self._x_to_ms(max(0.0, min(float(mx), float(self.width()))), self.width())
                # Right-edge drags: mouse is at the visual edge which is
                # kf.timestamp + kf.duration, so subtract duration to get
                # the actual timestamp the keyframe should move to.
                if self._drag_edge_is_right:
                    kf = next((k for k in self.keyframes if k.id == self._drag_kf_id), None)
                    if kf:
                        new_time = new_time - kf.duration
                self.keyframe_moved.emit(self._drag_kf_id, new_time)
                return
            elif self._drag_mode == "body" and self._drag_body_ids:
                # Only start actual drag if mouse moved more than a few pixels
                if self._press_pos and not self._drag_actually_moved:
                    delta = (event.position() - self._press_pos).manhattanLength()
                    if delta < 4:
                        return  # not a real drag yet
                    self._drag_actually_moved = True
                click_ms = self._x_to_ms(mx, self.width())
                new_start = click_ms - self._drag_body_offset
                eff_start = self._eff_start
                eff_end = self._eff_end
                new_start = max(eff_start, min(new_start, eff_end - self._drag_body_seg_duration))
                new_end = new_start + self._drag_body_seg_duration
                # Move both keyframes
                start_id, end_id = self._drag_body_ids
                if start_id:
                    self.keyframe_moved.emit(start_id, new_start)
                if end_id:
                    self.keyframe_moved.emit(end_id, new_end)
                return
            elif self._drag_mode == "pan_point" and self._drag_kf_id:
                new_time = self._x_to_ms(max(0.0, min(float(mx), float(self.width()))), self.width())
                # Clamp to segment bounds: find start and end of parent segment
                seg_start_kf = next((k for k in self.keyframes if k.id == self._drag_pan_seg_id), None)
                if seg_start_kf:
                    sorted_kfs = sorted(self.keyframes, key=lambda k: k.timestamp)
                    seg_end_kf = None
                    found_start = False
                    for k in sorted_kfs:
                        if k.id == self._drag_pan_seg_id:
                            found_start = True
                            continue
                        if found_start and k.zoom <= 1.01:
                            seg_end_kf = k
                            break
                    min_t = seg_start_kf.timestamp + 100
                    max_t = (seg_end_kf.timestamp - 100) if seg_end_kf else self._eff_end - 100
                    new_time = max(min_t, min(new_time, max_t))
                self.keyframe_moved.emit(self._drag_kf_id, new_time)
                return
            elif self._drag_mode == "voiceover" and self._drag_kf_id:
                new_time = self._x_to_ms(max(0.0, min(float(mx), float(self.width()))), self.width())
                new_time = max(self._eff_start, new_time - self._drag_body_offset)
                new_time = min(new_time, self._eff_end)
                if self._press_pos and (
                    abs(mx - self._press_pos.x()) > 3
                    or abs(my - self._press_pos.y()) > 3
                ):
                    self._drag_actually_moved = True
                if self._drag_actually_moved:
                    self.voiceover_moved.emit(self._drag_kf_id, new_time)
                return

        # Update cursor based on hover over edge handles, trim handles, pan points, or segment body
        # Check pan point hover
        pan_hover = False
        for cx, cy, r, pp_kf_id, seg_start_id in self._pan_point_markers:
            if (mx - cx) ** 2 + (my - cy) ** 2 <= (r + 3) ** 2:
                pan_hover = True
                break
        edge_hit = self._edge_hit_test(mx, my)
        trim_hit = self._trim_hit_test(mx)
        if pan_hover:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif edge_hit:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif trim_hit:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif self._segment_body_hit_info(mx, my):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._voiceover_hit_test(mx, my):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._video_seg_hit_test(mx, my):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            was_body_drag = self._drag_mode == "body"
            if self._dragging:
                self.drag_finished.emit()
            self._dragging = False
            self._drag_kf_id = None
            self._drag_mode = ""
            self._drag_body_ids = []
            self._trim_snapped = False
            # If user clicked a segment body without dragging, select it
            # so Delete key can remove it.
            if was_body_drag and not self._drag_actually_moved and self._pending_select_id:
                self._selected_segment_id = self._pending_select_id
                self._selected_click_idx = -1
                self.update()
            self._pending_select_id = ""
            self._press_pos = None

    def _click_hit_test(self, x: float, y: float) -> int:
        """Check if position is over a click event marker.
        Returns the index into click_events, or -1."""
        if not self.click_events or self._eff_dur <= 0:
            return -1
        if y < self._click_top or y > self._click_top + self._click_h:
            return -1
        mid_y = self._click_top + self._click_h / 2.0
        w = self.width()
        grab = self.CLICK_HIT_PX
        eff_start = self._eff_start
        eff_end = self._eff_end
        for i, ev in enumerate(self.click_events):
            if ev.timestamp < eff_start or ev.timestamp > eff_end:
                continue
            ex = self._ms_to_x(ev.timestamp, w)
            if abs(x - ex) <= grab and abs(y - mid_y) <= grab:
                return i
        return -1

    def _delete_selected_click(self) -> None:
        """Delete the currently selected click event."""
        if self._selected_click_idx >= 0 and self._selected_click_idx < len(self.click_events):
            self.click_event_deleted.emit(self._selected_click_idx)
            self._selected_click_idx = -1
            self.update()

    def _delete_selected_voiceover(self) -> None:
        """Delete the currently selected voiceover segment."""
        if self._selected_vo_id:
            vid = self._selected_vo_id
            self._selected_vo_id = ""
            self.voiceover_clicked.emit(vid)  # main_window handles via edit dialog
            self.update()

    def _delete_selected_video_segment(self) -> None:
        """Delete the currently selected video segment (if more than one remains)."""
        if self._selected_video_seg_id and len(self.video_segments) > 1:
            vid = self._selected_video_seg_id
            self._selected_video_seg_id = ""
            self.video_segment_deleted.emit(vid)
            self.update()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_S and not event.modifiers():
            if self.duration > 0:
                self.split_requested.emit(self.current_time)
                return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # Video segment deletion takes priority when selected
            if self._selected_video_seg_id:
                self._delete_selected_video_segment()
                return
            if self._selected_segment_id:
                sid = self._selected_segment_id
                self._selected_segment_id = ""
                self.segment_deleted.emit(sid)
                self.update()
                return
            if self._selected_vo_id:
                vid = self._selected_vo_id
                self._selected_vo_id = ""
                self.voiceover_deleted.emit(vid)
                self.update()
                return
            if self._selected_click_idx >= 0:
                self._delete_selected_click()
                return
        super().keyPressEvent(event)


class TimelineWidget(QWidget):
    """Full timeline component — Clipchamp-style with centered playback controls."""

    seek_requested = Signal(float)      # time in ms
    keyframe_moved = Signal(str, float) # kf id, new timestamp ms
    segment_clicked = Signal(str, float) # (start kf id, click timestamp ms)
    segment_deleted = Signal(str)       # start kf id of segment to delete
    play_pause_clicked = Signal()       # toggle playback
    click_event_deleted = Signal(int)   # click event index to delete
    pan_point_clicked = Signal(str, str) # (pan kf id, segment start kf id)
    add_zoom_requested = Signal(float)  # timestamp ms — add zoom at this time
    add_voiceover_requested = Signal(float)  # timestamp ms — add voiceover here
    voiceover_clicked = Signal(str)       # voiceover segment id — edit
    voiceover_deleted = Signal(str)       # voiceover segment id — delete
    voiceover_moved = Signal(str, float)  # voiceover segment id, new timestamp ms
    video_segment_deleted = Signal(str)   # video segment id — delete
    split_requested = Signal(float)       # timestamp ms — split recording here
    trim_changed = Signal(float, float) # (trim_start_ms, trim_end_ms)
    trim_reset = Signal()               # reset both trim handles to full range
    drag_finished = Signal()            # emitted when any drag completes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TimelineArea")
        self._is_playing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 6)
        layout.setSpacing(4)

        # ── Playback controls row (centered, like Clipchamp) ────
        controls_row = QHBoxLayout()
        controls_row.setSpacing(6)

        controls_row.addStretch()

        # skip to start
        self._btn_skip_start = QPushButton("⏮")
        self._btn_skip_start.setObjectName("SkipBtn")
        self._btn_skip_start.setToolTip("Go to start")
        self._btn_skip_start.clicked.connect(self._seek_start)
        controls_row.addWidget(self._btn_skip_start)

        # play/pause
        self._play_btn = QPushButton("▶")
        self._play_btn.setObjectName("PlayBtn")
        self._play_btn.setToolTip("Play / Pause")
        self._play_btn.clicked.connect(self._on_play_pause)
        controls_row.addWidget(self._play_btn)

        # skip to end
        self._btn_skip_end = QPushButton("⏭")
        self._btn_skip_end.setObjectName("SkipBtn")
        self._btn_skip_end.setToolTip("Go to end")
        self._btn_skip_end.clicked.connect(lambda: self._seek_end())
        controls_row.addWidget(self._btn_skip_end)

        controls_row.addSpacing(12)

        # time display: current / total
        self._time_current = QLabel("0:00.00")
        self._time_current.setObjectName("TimeDisplay")
        controls_row.addWidget(self._time_current)

        time_sep = QLabel(" / ")
        time_sep.setObjectName("TimeDisplayDim")
        controls_row.addWidget(time_sep)

        self._time_total = QLabel("0:00.00")
        self._time_total.setObjectName("TimeDisplayDim")
        controls_row.addWidget(self._time_total)

        controls_row.addStretch()

        layout.addLayout(controls_row)

        # ── Track ───────────────────────────────────────────────
        self._track = _TimelineTrack()
        self._track.clicked.connect(self._on_click)
        self._track.keyframe_moved.connect(self.keyframe_moved)
        self._track.segment_clicked.connect(self.segment_clicked)
        self._track.segment_deleted.connect(self.segment_deleted)
        self._track.click_event_deleted.connect(self.click_event_deleted)
        self._track.pan_point_clicked.connect(self.pan_point_clicked)
        self._track.add_zoom_requested.connect(self.add_zoom_requested)
        self._track.add_voiceover_requested.connect(self.add_voiceover_requested)
        self._track.voiceover_clicked.connect(self.voiceover_clicked)
        self._track.voiceover_deleted.connect(self.voiceover_deleted)
        self._track.voiceover_moved.connect(self.voiceover_moved)
        self._track.video_segment_deleted.connect(self.video_segment_deleted)
        self._track.split_requested.connect(self.split_requested)
        self._track.trim_changed.connect(self.trim_changed)
        self._track.trim_reset.connect(self.trim_reset)
        self._track.drag_finished.connect(self.drag_finished)
        self._track.view_changed.connect(self._sync_scrollbar)
        layout.addWidget(self._track)

        # ── Horizontal scrollbar (visible only when zoomed in) ──
        self._hscroll = QScrollBar(Qt.Orientation.Horizontal)
        self._hscroll.setObjectName("TimelineScrollBar")
        self._hscroll.setVisible(False)
        self._hscroll.valueChanged.connect(self._on_scrollbar)
        layout.addWidget(self._hscroll)

        # ── Bottom hints ────────────────────────────────────────
        hints_row = QHBoxLayout()
        hint_kf = QLabel("Right-click zoom segment to edit · Click to select · Del to delete · Drag edges to trim · S to split")
        hint_kf.setObjectName("Muted")
        hints_row.addWidget(hint_kf)
        hints_row.addStretch()
        layout.addLayout(hints_row)

    def _seek_start(self) -> None:
        """Seek to the effective start of the visible (trimmed) range."""
        self.seek_requested.emit(self._track._eff_start)

    def _seek_end(self) -> None:
        """Seek to the effective end of the visible (trimmed) range."""
        if self._track.duration > 0:
            self.seek_requested.emit(self._track._eff_end)

    def _sync_scrollbar(self) -> None:
        """Update scrollbar range/position to match the track's view state."""
        track = self._track
        if track.view_scale <= 1.0:
            self._hscroll.setVisible(False)
            return
        self._hscroll.setVisible(True)
        visible_duration = track.duration / track.view_scale
        max_offset = track.duration - visible_duration
        # Use integer steps (1 step = 1 ms) for fine granularity
        self._hscroll.blockSignals(True)
        self._hscroll.setMinimum(0)
        self._hscroll.setMaximum(int(max_offset))
        self._hscroll.setPageStep(int(visible_duration))
        self._hscroll.setValue(int(track.view_offset))
        self._hscroll.blockSignals(False)

    def _on_scrollbar(self, value: int) -> None:
        """Scroll the timeline track when the user moves the scrollbar."""
        self._track.set_view_offset(float(value))

    def reset_view(self) -> None:
        """Reset the timeline zoom to fit-all."""
        self._track.reset_view()
        self._hscroll.setVisible(False)

    def set_data(
        self,
        duration: float,
        current_time: float,
        keyframes: List[ZoomKeyframe],
        mouse_track: List[MousePosition],
        key_events: List[KeyEvent] | None = None,
        click_events: List[ClickEvent] | None = None,
        trim_start_ms: float = 0.0,
        trim_end_ms: float = 0.0,
        voiceover_segments: List[VoiceoverSegment] | None = None,
        video_segments: List[VideoSegment] | None = None,
    ) -> None:
        """Push new session data into the timeline and repaint."""
        self._track.duration = duration
        self._track.current_time = current_time
        self._track.keyframes = keyframes
        self._track.mouse_track = mouse_track
        if key_events is not None:
            self._track.key_events = key_events
        if click_events is not None:
            self._track.click_events = click_events
        self._track.trim_start_ms = trim_start_ms
        self._track.trim_end_ms = trim_end_ms
        if voiceover_segments is not None:
            self._track.voiceover_segments = voiceover_segments
        if video_segments is not None:
            self._track.video_segments = video_segments
        self._time_current.setText(_fmt_precise(current_time))
        self._time_total.setText(_fmt_precise(duration))
        # Clamp view state after duration changes (scale may exceed new max)
        self._track._clamp_view()
        self._sync_scrollbar()
        self._track.update()

    def set_playing(self, playing: bool) -> None:
        """Update the play/pause button icon to reflect playback state."""
        self._is_playing = playing
        self._play_btn.setText("⏸" if playing else "▶")
        self._play_btn.setToolTip("Pause" if playing else "Play")

    def _on_play_pause(self) -> None:
        self.play_pause_clicked.emit()

    def _on_click(self, time_ms: float) -> None:
        """Handle click on timeline track — time_ms is the absolute timestamp."""
        self.seek_requested.emit(time_ms)
