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
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu

from ..models import ZoomKeyframe, MousePosition, KeyEvent, ClickEvent
from ..utils import fmt_time as _fmt


def _fmt_precise(ms: float) -> str:
    total_s = ms / 1000
    m = int(total_s) // 60
    s = int(total_s) % 60
    cs = int((total_s - int(total_s)) * 100)
    return f"{m}:{s:02d}.{cs:02d}"


class _TimelineTrack(QWidget):
    """Custom-painted track showing heatmap, zoom segments, keyframes, and playhead."""

    clicked = Signal(float)  # time ratio 0–1
    keyframe_moved = Signal(str, float)  # keyframe id, new timestamp (ms)
    segment_clicked = Signal(str)        # start keyframe id of clicked segment
    segment_deleted = Signal(str)        # start keyframe id of segment to delete
    click_event_deleted = Signal(int)    # index of click event to delete
    trim_changed = Signal(float, float)  # (trim_start_ms, trim_end_ms)
    drag_finished = Signal()             # emitted when any drag completes

    EDGE_GRAB_PX = 6  # pixel tolerance for grabbing a segment edge
    CLICK_HIT_PX = 8  # pixel tolerance for clicking on a click marker
    TRIM_GRAB_PX = 8  # pixel tolerance for grabbing a trim handle

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setMaximumHeight(140)
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
        self.trim_start_ms: float = 0.0
        self.trim_end_ms: float = 0.0  # 0 = no trim

        # Drag state for zoom segment resizing / moving
        self._drag_kf_id: str | None = None    # which keyframe is being dragged
        self._dragging: bool = False
        self._drag_mode: str = ""              # "edge" | "body" | "trim_start" | "trim_end"
        self._drag_body_ids: list = []          # [start_kf_id, end_kf_id] for body drag
        self._drag_body_offset: float = 0.0     # ms offset from click to segment start
        self._drag_body_seg_duration: float = 0  # original segment duration in ms
        self._segments: List[tuple] = []       # [(start_x, end_x, start_kf_id, end_kf_id)]
        self._seg_top: int = 0
        self._seg_h: int = 0

        # Click event selection
        self._selected_click_idx: int = -1     # index into click_events, -1 = none
        self._click_top: int = 0               # y-offset for click track
        self._click_h: int = 0                 # height of click track

        # Zoom segment selection
        self._selected_segment_id: str = ""     # start kf id of selected segment
        # Track mouse press position to distinguish click from drag
        self._press_pos: QPointF | None = None
        self._drag_actually_moved: bool = False
        self._pending_select_id: str = ""       # segment to select on release if no drag

    def _on_right_click(self, pos) -> None:
        """Right-click on a zoom segment or click event opens context menu."""
        mx, my = pos.x(), pos.y()
        # Check zoom segment first
        seg_info = self._segment_body_hit_info(mx, my)
        if seg_info:
            start_id, end_id, sx, ex = seg_info
            self.segment_clicked.emit(start_id)
            return
        # Check click event marker
        click_idx = self._click_hit_test(mx, my)
        if click_idx >= 0:
            self._selected_click_idx = click_idx
            self.update()
            menu = QMenu(self)
            menu.setStyleSheet(
                "QMenu { background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58; padding: 4px; }"
                "QMenu::item { padding: 6px 20px; }"
                "QMenu::item:selected { background: #8b5cf6; }"
            )
            del_act = menu.addAction("🗑 Delete click event")
            del_act.triggered.connect(lambda: self._delete_selected_click())
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
        self._seg_h = h - self._seg_top - 4
        self._draw_zoom_segments(painter, w, self._seg_top, self._seg_h)

        # playhead
        px = (self.current_time / self.duration) * w
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawLine(int(px), 0, int(px), h)
        # playhead handle
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(px, 0), 5, 5)

        # ── Trim handles ───────────────────────────────────────────
        self._draw_trim_handles(painter, w, h)

        painter.end()

    def _draw_time_markers(self, painter: QPainter, w: int) -> None:
        if self.duration <= 0:
            return
        # draw tick marks every 5 seconds
        interval_ms = 5000
        if self.duration < 30000:
            interval_ms = 5000
        elif self.duration < 120000:
            interval_ms = 10000
        else:
            interval_ms = 30000

        font = QFont()
        font.setFamily("Segoe UI Variable")
        font.setPixelSize(11)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#5a5873"), 1))

        t = 0.0
        while t <= self.duration:
            x = (t / self.duration) * w
            painter.drawLine(int(x), 0, int(x), 4)
            if t > 0 and x < w - 30:
                painter.drawText(int(x) + 2, 12, _fmt(t))
            t += interval_ms

    def _draw_mouse_track(self, painter: QPainter, w: int, top: int, h: int) -> None:
        """Draw mouse speed heatmap — purple gradient."""
        track = self.mouse_track
        dur = self.duration
        if len(track) < 2 or dur <= 0:
            return

        # Track label
        label_font = QFont()
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        painter.setPen(QPen(QColor("#6c6890"), 1))
        painter.drawText(4, top + h - 3, "Mouse")

        buckets = min(w, 200)
        speeds = [0.0] * buckets
        max_speed = 0.0

        for i in range(1, len(track)):
            prev, curr = track[i - 1], track[i]
            dx = curr.x - prev.x
            dy = curr.y - prev.y
            dt = max(curr.timestamp - prev.timestamp, 1)
            speed = math.sqrt(dx * dx + dy * dy) / dt
            bucket = min(buckets - 1, int((curr.timestamp / dur) * buckets))
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
        dur = self.duration
        events = self.key_events
        if not events or dur <= 0:
            return

        # Track label
        label_font = QFont()
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        painter.setPen(QPen(QColor("#6c6890"), 1))
        painter.drawText(4, top + h - 2, "Keys")

        buckets = min(w, 200)
        counts = [0] * buckets
        max_count = 0

        for ev in events:
            bucket = min(buckets - 1, int((ev.timestamp / dur) * buckets))
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
        dur = self.duration
        events = self.click_events
        if not events or dur <= 0:
            return

        # Track label
        label_font = QFont()
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(10)
        painter.setFont(label_font)
        painter.setPen(QPen(QColor("#6c6890"), 1))
        painter.drawText(4, top + h - 2, "Clicks")

        mid_y = top + h / 2.0
        for i, ev in enumerate(events):
            x = (ev.timestamp / dur) * w
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
        if not self.keyframes or self.duration <= 0:
            return

        # Build segments directly from keyframe pairs instead of sampling
        # to avoid precision issues where close blocks merge visually.
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
                    end_ms = end_kf.timestamp + end_kf.duration
                    end_id = end_kf.id
                    i = j + 1
                else:
                    # No zoom-out found — block extends to end of video
                    end_ms = self.duration
                    end_id = ""
                    i = len(sorted_kfs)
                sx = (start_ms / self.duration) * w
                ex = (end_ms / self.duration) * w
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
            if kf_in and self.duration > 0:
                kf_in_x = (kf_in.timestamp / self.duration) * w
                # End of zoom-in transition
                kf_in_end_x = ((kf_in.timestamp + kf_in.duration) / self.duration) * w
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
            if kf_out and self.duration > 0:
                kf_out_x = (kf_out.timestamp / self.duration) * w
                kf_out_end_x = ((kf_out.timestamp + kf_out.duration) / self.duration) * w
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
            if kf_in and self.duration > 0:
                label_left = max(label_left, ((kf_in.timestamp + kf_in.duration) / self.duration) * w + 4)
            label_right = ex - 6
            if kf_out and self.duration > 0:
                label_right = min(label_right, (kf_out.timestamp / self.duration) * w - 4)
            label_w = label_right - label_left
            if label_w > 40:
                painter.setPen(QPen(QColor("#a78bfa")))
                text_rect = QRectF(label_left, top, label_w, h)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "🔍 Zoom")

            # Draw edge handles (vertical bars at edges)
            handle_color = QColor("#c4b5fd") if not self._dragging else QColor("#e9d5ff")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(handle_color))
            handle_w = 3
            # Left handle
            painter.drawRoundedRect(QRectF(sx, top + 2, handle_w, h - 4), 1, 1)
            # Right handle
            painter.drawRoundedRect(QRectF(ex - handle_w, top + 2, handle_w, h - 4), 1, 1)

    # ── trim handles ──────────────────────────────────────────────

    def _draw_trim_handles(self, painter: QPainter, w: int, h: int) -> None:
        """Draw trim handle bars at the timeline edges and dimmed overlays
        for any trimmed-out regions."""
        if self.duration <= 0:
            return
        trim_s = self.trim_start_ms
        trim_e = self.trim_end_ms if self.trim_end_ms > 0 else self.duration

        # Dimmed overlay for trimmed-out regions
        dim_color = QColor(20, 18, 40, 160)
        if trim_s > 0:
            sx = (trim_s / self.duration) * w
            painter.fillRect(QRectF(0, 0, sx, h), dim_color)
        if trim_e < self.duration:
            ex = (trim_e / self.duration) * w
            painter.fillRect(QRectF(ex, 0, w - ex, h), dim_color)

        # Handle bars — always visible at the trim positions
        handle_w = 4
        handle_color = QColor("#facc15")  # yellow accent
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(handle_color))

        # Left (start) trim handle
        sx = (trim_s / self.duration) * w if trim_s > 0 else 0
        painter.drawRoundedRect(QRectF(sx, 0, handle_w, h), 2, 2)
        painter.setPen(QPen(QColor("#1b1a2e"), 1.5))
        # tick marks on the handle
        mid_y = h / 2
        painter.drawLine(int(sx) + 1, int(mid_y) - 6, int(sx) + 1, int(mid_y) + 6)
        painter.drawLine(int(sx) + 3, int(mid_y) - 6, int(sx) + 3, int(mid_y) + 6)
        painter.setPen(Qt.PenStyle.NoPen)

        # Right (end) trim handle
        ex = (trim_e / self.duration) * w if trim_e < self.duration else w
        painter.setBrush(QBrush(handle_color))
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
        trim_s = self.trim_start_ms
        trim_e = self.trim_end_ms if self.trim_end_ms > 0 else self.duration

        # Left handle — always at x=0 when trim_s==0, else at the trim position
        sx = (trim_s / self.duration) * w if trim_s > 0 else 0
        if abs(x - sx) <= grab:
            return "trim_start"
        # Right handle — always at x=w when trim_e==duration, else at the trim position
        ex = (trim_e / self.duration) * w if trim_e < self.duration else w
        if abs(x - ex) <= grab:
            return "trim_end"
        return ""

    # ── mouse events ────────────────────────────────────────────────

    def _edge_hit_test(self, x: float, y: float) -> str | None:
        """Check if the mouse is over a segment edge handle.
        Returns the keyframe id to drag, or None."""
        if y < self._seg_top or y > self._seg_top + self._seg_h:
            return None
        grab = self.EDGE_GRAB_PX
        for sx, ex, start_id, end_id in self._segments:
            if abs(x - sx) <= grab and start_id:
                return start_id
            if abs(x - ex) <= grab and end_id:
                return end_id
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
            # Check zoom segment edge drag first — takes priority over trim handles so
            # that blocks touching the video boundaries (x=0 or x=width) remain resizable.
            kf_id = self._edge_hit_test(mx, my)
            if kf_id:
                self._dragging = True
                self._drag_mode = "edge"
                self._drag_kf_id = kf_id
                self._selected_click_idx = -1
                self._selected_segment_id = ""
                return
            # Check segment body drag (move entire segment)
            seg_info = self._segment_body_hit_info(mx, my)
            if seg_info:
                start_id, end_id, sx, ex = seg_info
                click_ms = (mx / self.width()) * self.duration
                # Use actual keyframe timestamps (not visual segment extent)
                # to prevent the segment from growing on each drag cycle.
                start_kf = next((k for k in self.keyframes if k.id == start_id), None)
                end_kf = next((k for k in self.keyframes if k.id == end_id), None) if end_id else None
                if start_kf:
                    kf_start_ms = start_kf.timestamp
                    kf_end_ms = end_kf.timestamp if end_kf else kf_start_ms
                else:
                    kf_start_ms = (sx / self.width()) * self.duration
                    kf_end_ms = (ex / self.width()) * self.duration
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
                self._selected_click_idx = -1
                self._selected_segment_id = ""
                return
            # Check click event selection
            click_idx = self._click_hit_test(mx, my)
            if click_idx >= 0:
                self._selected_click_idx = click_idx
                self._selected_segment_id = ""
                self.update()
                return
            # Regular click — seek (and deselect any click/segment)
            self._selected_click_idx = -1
            self._selected_segment_id = ""
            ratio = max(0.0, min(1.0, mx / self.width()))
            self.clicked.emit(ratio)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        mx = event.position().x()
        my = event.position().y()

        if self._dragging and self.duration > 0:
            if self._drag_mode == "trim_start":
                ratio = max(0.0, min(1.0, mx / self.width()))
                new_time = ratio * self.duration
                trim_e = self.trim_end_ms if self.trim_end_ms > 0 else self.duration
                new_time = min(new_time, trim_e - 500)  # keep at least 500ms
                self.trim_start_ms = max(0.0, new_time)
                self.trim_changed.emit(self.trim_start_ms, self.trim_end_ms)
                self.update()
                return
            elif self._drag_mode == "trim_end":
                ratio = max(0.0, min(1.0, mx / self.width()))
                new_time = ratio * self.duration
                new_time = max(new_time, self.trim_start_ms + 500)
                self.trim_end_ms = min(self.duration, new_time)
                self.trim_changed.emit(self.trim_start_ms, self.trim_end_ms)
                self.update()
                return
            elif self._drag_mode == "edge" and self._drag_kf_id:
                ratio = max(0.0, min(1.0, mx / self.width()))
                new_time = ratio * self.duration
                self.keyframe_moved.emit(self._drag_kf_id, new_time)
                return
            elif self._drag_mode == "body" and self._drag_body_ids:
                # Only start actual drag if mouse moved more than a few pixels
                if self._press_pos and not self._drag_actually_moved:
                    delta = (event.position() - self._press_pos).manhattanLength()
                    if delta < 4:
                        return  # not a real drag yet
                    self._drag_actually_moved = True
                click_ms = (mx / self.width()) * self.duration
                new_start = click_ms - self._drag_body_offset
                new_start = max(0.0, min(new_start, self.duration - self._drag_body_seg_duration))
                new_end = new_start + self._drag_body_seg_duration
                # Move both keyframes
                start_id, end_id = self._drag_body_ids
                if start_id:
                    self.keyframe_moved.emit(start_id, new_start)
                if end_id:
                    self.keyframe_moved.emit(end_id, new_end)
                return

        # Update cursor based on hover over edge handles, trim handles, or segment body
        kf_id = self._edge_hit_test(mx, my)
        trim_hit = self._trim_hit_test(mx)
        if kf_id:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif trim_hit:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif self._segment_body_hit_info(mx, my):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
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
        if not self.click_events or self.duration <= 0:
            return -1
        if y < self._click_top or y > self._click_top + self._click_h:
            return -1
        mid_y = self._click_top + self._click_h / 2.0
        w = self.width()
        grab = self.CLICK_HIT_PX
        for i, ev in enumerate(self.click_events):
            ex = (ev.timestamp / self.duration) * w
            if abs(x - ex) <= grab and abs(y - mid_y) <= grab:
                return i
        return -1

    def _delete_selected_click(self) -> None:
        """Delete the currently selected click event."""
        if self._selected_click_idx >= 0 and self._selected_click_idx < len(self.click_events):
            self.click_event_deleted.emit(self._selected_click_idx)
            self._selected_click_idx = -1
            self.update()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._selected_segment_id:
                sid = self._selected_segment_id
                self._selected_segment_id = ""
                self.segment_deleted.emit(sid)
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
    segment_clicked = Signal(str)       # start kf id of clicked segment
    segment_deleted = Signal(str)       # start kf id of segment to delete
    play_pause_clicked = Signal()       # toggle playback
    click_event_deleted = Signal(int)   # click event index to delete
    trim_changed = Signal(float, float) # (trim_start_ms, trim_end_ms)
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
        self._btn_skip_start.clicked.connect(lambda: self.seek_requested.emit(0))
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
        self._track.trim_changed.connect(self.trim_changed)
        self._track.drag_finished.connect(self.drag_finished)
        layout.addWidget(self._track)

        # ── Bottom hints ────────────────────────────────────────
        hints_row = QHBoxLayout()
        hint_kf = QLabel("Right-click zoom segment to edit · Click to select · Del to delete · Drag edges to trim")
        hint_kf.setObjectName("Muted")
        hints_row.addWidget(hint_kf)
        hints_row.addStretch()
        layout.addLayout(hints_row)

    def _seek_end(self) -> None:
        if self._track.duration > 0:
            self.seek_requested.emit(self._track.duration)

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
    ) -> None:
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
        self._time_current.setText(_fmt_precise(current_time))
        self._time_total.setText(_fmt_precise(duration))
        self._track.update()

    def set_playing(self, playing: bool) -> None:
        self._is_playing = playing
        self._play_btn.setText("⏸" if playing else "▶")
        self._play_btn.setToolTip("Pause" if playing else "Play")

    def _on_play_pause(self) -> None:
        self.play_pause_clicked.emit()

    def _on_click(self, ratio: float) -> None:
        time_ms = ratio * self._track.duration
        self.seek_requested.emit(time_ms)
