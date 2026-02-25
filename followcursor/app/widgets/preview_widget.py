"""Preview widget — displays live capture or video playback with floating window effect."""

import logging
from typing import List, Optional, Tuple
import bisect
import time as _time

logger = logging.getLogger(__name__)
import cv2
import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal, QPointF, QRectF
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import QWidget, QMenu

from ..models import MousePosition, ClickEvent, ZoomKeyframe


class PreviewWidget(QWidget):
    """Central preview canvas — displays live capture or recorded video.

    Renders the full compositor scene (background + bezel + video +
    cursor/click overlays) via QPainter.  Supports zoom/pan, debug
    overlay, centroid-pick mode, and video playback with wall-clock
    timing.
    """

    # Signal: (timestamp_ms, zoom_level, pan_x, pan_y)
    zoom_at_requested = Signal(float, float, float, float)
    # Signal: (pan_x, pan_y) — emitted when centroid-pick mode click occurs
    centroid_picked = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PreviewWidget")
        self.setMinimumSize(480, 270)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._frame: Optional[QImage] = None
        self._zoom: float = 1.0
        self._pan_x: float = 0.5
        self._pan_y: float = 0.5

        # mouse cursor overlay data
        self._mouse_track: List[MousePosition] = []
        self._click_events: List[ClickEvent] = []
        self._monitor_rect: Optional[dict] = None
        self._current_time_ms: float = 0.0

        # debug overlay
        self._debug_overlay: bool = False
        self._debug_keyframes: List[ZoomKeyframe] = []

        # background preset
        self._bg_preset = None  # None → use default
        self._frame_preset = None  # None → use default frame

        # recording overlay
        self._recording_mode: bool = False
        self._blurred_frame: Optional[QImage] = None

        # output dimensions (for aspect-ratio preview)
        self._output_dim = "auto"  # "auto" or (w, h) tuple

        # centroid-pick mode: when True, next left-click picks centroid
        self._centroid_pick_mode: bool = False

        # playback state
        self._video_cap: Optional[cv2.VideoCapture] = None
        self._playback_timer = QTimer(self)
        self._playback_timer.timeout.connect(self._advance_playback)
        self._playing: bool = False
        self._video_fps: float = 30.0
        self._video_duration_ms: float = 0.0
        self._playback_pos_ms: float = 0.0
        # Wall-clock anchors for accurate playback speed
        self._play_start_wall: float = 0.0
        self._play_start_pos_ms: float = 0.0
        self._last_displayed_frame: int = -1
        self._frame_timestamps: Optional[List[float]] = None  # per-frame ms offsets

    # ── public API ──────────────────────────────────────────────────

    def set_frame(self, frame: QImage) -> None:
        """Called from live capture to update the display."""
        self._frame = frame
        self.update()

    def set_zoom(self, zoom: float, pan_x: float, pan_y: float) -> None:
        """Update the current zoom level and pan position for rendering."""
        self._zoom = zoom
        self._pan_x = pan_x
        self._pan_y = pan_y
        self.update()

    def set_cursor_data(
        self,
        mouse_track: List[MousePosition],
        monitor_rect: dict,
        click_events: Optional[List[ClickEvent]] = None,
    ) -> None:
        """Provide mouse track + monitor rect for cursor overlay."""
        self._mouse_track = mouse_track
        self._monitor_rect = monitor_rect
        self._click_events = click_events or []

    def set_current_time(self, time_ms: float) -> None:
        """Set the current playback time for cursor positioning."""
        self._current_time_ms = time_ms

    def set_bg_preset(self, preset) -> None:
        """Set the background preset for the compositor."""
        self._bg_preset = preset
        self.update()

    def set_frame_preset(self, preset) -> None:
        """Set the device frame preset for the compositor."""
        self._frame_preset = preset
        self.update()

    def set_output_dim(self, dim) -> None:
        """Set output dimensions for aspect-ratio preview.

        *dim* — ``'auto'`` or ``(width, height)`` tuple.
        """
        self._output_dim = dim
        self.update()

    def set_debug_overlay(self, enabled: bool) -> None:
        """Enable/disable the zoom debug overlay."""
        self._debug_overlay = enabled
        self.update()

    def set_debug_keyframes(self, keyframes: List[ZoomKeyframe]) -> None:
        """Provide keyframes for the debug overlay."""
        self._debug_keyframes = keyframes
        if self._debug_overlay:
            self.update()

    def set_recording_mode(self, enabled: bool) -> None:
        """Enable/disable recording overlay (blurred snapshot + indicator)."""
        if enabled and self._frame is not None:
            self._blurred_frame = self._blur_frame(self._frame)
        self._recording_mode = enabled
        if not enabled:
            self._blurred_frame = None
        self.update()

    def enter_centroid_pick_mode(self) -> None:
        """Enter centroid-pick mode: next left-click picks a pan coordinate."""
        self._centroid_pick_mode = True
        self.setCursor(Qt.CursorShape.CrossCursor)

    def cancel_centroid_pick(self) -> None:
        """Cancel centroid-pick mode without emitting."""
        self._centroid_pick_mode = False
        self.unsetCursor()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if (
            self._centroid_pick_mode
            and event.button() == Qt.MouseButton.LeftButton
        ):
            pan_x, pan_y = self._click_to_pan(
                event.position().x(), event.position().y()
            )
            self._centroid_pick_mode = False
            self.unsetCursor()
            if pan_x >= 0:
                self.centroid_picked.emit(pan_x, pan_y)
            return
        super().mousePressEvent(event)

    def load_video(
        self, path: str, actual_fps: float = 0.0, duration_ms: float = 0.0,
        frame_timestamps: Optional[List[float]] = None,
    ) -> float:
        """Load video for playback. Returns duration in ms.

        *actual_fps* — if provided, overrides the FPS from video metadata
        (MJPG AVI on Windows sometimes stores incorrect FPS values).

        *duration_ms* — if provided, overrides the frame-count-based
        duration.  Use the wall-clock recording duration here because
        ``CAP_PROP_FRAME_COUNT`` is unreliable for lossless AVI codecs
        like huffyuv.
        """
        self.stop_playback()
        self._video_cap = cv2.VideoCapture(path)
        if not self._video_cap.isOpened():
            self._video_cap = None
            return 0.0
        meta_fps = self._video_cap.get(cv2.CAP_PROP_FPS)
        cap_frame_count = int(self._video_cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # After a post-recording remux the metadata FPS is correct.
        # For legacy / project-file videos that were NOT remuxed, the
        # metadata may still be wrong (e.g. 60 fps for a 7 fps capture).
        # Detect this with a sanity check: if the metadata-based duration
        # and the wall-clock duration disagree by > 10 %, count real frames.
        meta_dur = (cap_frame_count / meta_fps * 1000) if meta_fps > 0 else 0
        need_recount = False
        if duration_ms > 0 and meta_dur > 0:
            ratio = meta_dur / duration_ms
            if ratio < 0.90 or ratio > 1.10:
                need_recount = True

        if need_recount:
            real_frame_count = 0
            while self._video_cap.grab():
                real_frame_count += 1
            self._video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            if duration_ms > 0 and real_frame_count > 0:
                self._video_fps = real_frame_count / (duration_ms / 1000.0)
            elif actual_fps > 0:
                self._video_fps = actual_fps
            else:
                self._video_fps = meta_fps or 30.0
            computed_dur = (real_frame_count / self._video_fps) * 1000 if self._video_fps > 0 else 0
            logger.info(
                "load_video (recounted): real_frames=%d cap_frame_count=%d "
                "meta_fps=%.1f video_fps=%.2f duration_ms=%.0f",
                real_frame_count, cap_frame_count, meta_fps,
                self._video_fps, duration_ms,
            )
        else:
            # Metadata is trustworthy (remuxed file or non-huffyuv)
            self._video_fps = actual_fps if actual_fps > 0 else (meta_fps or 30.0)
            computed_dur = (cap_frame_count / self._video_fps) * 1000 if self._video_fps > 0 else 0
            logger.info(
                "load_video: frames=%d meta_fps=%.1f video_fps=%.2f duration_ms=%.0f",
                cap_frame_count, meta_fps, self._video_fps,
                duration_ms if duration_ms > 0 else computed_dur,
            )

        self._video_duration_ms = duration_ms if duration_ms > 0 else computed_dur
        self._playback_pos_ms = 0.0
        self._frame_timestamps = frame_timestamps
        self.seek_to(0)
        return self._video_duration_ms

    def _time_to_frame(self, time_ms: float) -> int:
        """Map a playback time (ms) to the correct video frame index.

        When per-frame timestamps are available (variable-rate WGC
        recordings) this uses binary search.  Otherwise falls back to
        the uniform ``time * fps / 1000`` mapping.
        """
        if self._frame_timestamps:
            idx = bisect.bisect_right(self._frame_timestamps, time_ms) - 1
            return max(0, idx)
        return int(time_ms / 1000.0 * self._video_fps)

    def seek_to(self, time_ms: float) -> None:
        """Jump video playback to the given timestamp."""
        if self._video_cap and self._video_cap.isOpened():
            self._playback_pos_ms = time_ms
            target_frame = self._time_to_frame(time_ms)
            self._video_cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = self._video_cap.read()
            if ret:
                self._last_displayed_frame = target_frame
                self._frame = self._numpy_to_qimage(frame)
                self.update()
            # Reset wall-clock anchor so playback continues from here
            if self._playing:
                self._play_start_wall = _time.perf_counter()
                self._play_start_pos_ms = time_ms

    def play(self) -> None:
        """Start video playback from the current position."""
        if self._video_cap and not self._playing:
            # If at/near the end of the video, wrap back to the start
            if self._playback_pos_ms >= self._video_duration_ms - 100:
                self._playback_pos_ms = 0.0
            # Seek to the correct frame
            target_frame = self._time_to_frame(self._playback_pos_ms)
            self._video_cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            self._last_displayed_frame = max(target_frame - 1, -1)
            # Anchor wall-clock time for accurate playback speed
            self._play_start_wall = _time.perf_counter()
            self._play_start_pos_ms = self._playback_pos_ms
            self._playing = True
            # Use a fast timer (8ms) and select frames by wall-clock
            self._playback_timer.start(8)

    def pause(self) -> None:
        """Pause video playback."""
        self._playing = False
        self._playback_timer.stop()

    def stop_playback(self) -> None:
        self.pause()
        if self._video_cap:
            self._video_cap.release()
            self._video_cap = None

    @property
    def playback_pos_ms(self) -> float:
        return self._playback_pos_ms

    @property
    def video_duration_ms(self) -> float:
        return self._video_duration_ms

    @property
    def is_playing(self) -> bool:
        return self._playing

    # ── right-click context menu ────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        """Show single 'Add Zoom here' menu at click position."""
        if self._frame is None:
            return

        # Compute normalized pan coordinates from click position
        pan_x, pan_y = self._click_to_pan(pos.x(), pos.y())
        if pan_x < 0:  # click outside screen area
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58; }"
            "QMenu::item:selected { background: #8b5cf6; }"
        )

        time_ms = self._current_time_ms

        act_zoom = menu.addAction("🔍 Add Zoom here")
        act_zoom.triggered.connect(
            lambda: self.zoom_at_requested.emit(time_ms, 1.5, pan_x, pan_y)
        )

        menu.exec(self.mapToGlobal(pos))

    def _canvas_rect(self) -> Tuple[float, float, float, float]:
        """Return (x, y, w, h) of the virtual canvas within the widget.

        When output_dim is set, the canvas is letterboxed/pillarboxed to
        match the target aspect ratio.  When 'auto', the canvas matches
        the source frame's aspect ratio.  Falls back to filling the
        widget if no frame is loaded.
        """
        W, H = float(self.width()), float(self.height())

        if self._output_dim != "auto" and isinstance(self._output_dim, tuple):
            ow, oh = self._output_dim
            target_aspect = ow / oh
        elif self._frame is not None and self._frame.width() > 0 and self._frame.height() > 0:
            # Auto mode — use source aspect ratio
            target_aspect = self._frame.width() / self._frame.height()
        else:
            return 0.0, 0.0, W, H

        widget_aspect = W / max(H, 1)
        if widget_aspect > target_aspect:
            cw = H * target_aspect
            ch = H
        else:
            cw = W
            ch = W / target_aspect
        return (W - cw) / 2, (H - ch) / 2, cw, ch

    def _click_to_pan(self, click_x: float, click_y: float) -> tuple:
        """Map a widget click position to normalized (0-1) pan coordinates.

        Returns (pan_x, pan_y) or (-1, -1) if the click is outside the screen.
        Uses the same geometry math as the compositor.
        """
        from ..frames import DEFAULT_FRAME

        if self._frame is None:
            return -1.0, -1.0

        cx, cy, W, H = self._canvas_rect()
        # Translate click into canvas-local coordinates
        click_x -= cx
        click_y -= cy
        iw, ih = self._frame.width(), self._frame.height()
        if iw <= 0 or ih <= 0:
            return -1.0, -1.0

        fp = self._frame_preset or DEFAULT_FRAME
        video_aspect = iw / ih

        if fp.is_none:
            # No frame — video fills canvas (letterboxed)
            if W / H > video_aspect:
                scr_h = H
                scr_w = H * video_aspect
            else:
                scr_w = W
                scr_h = W / video_aspect
            scr_x = (W - scr_w) / 2
            scr_y = (H - scr_h) / 2
        else:
            pad_x = W * fp.padding
            pad_y = H * fp.padding
            avail_w = W - 2 * pad_x
            avail_h = H - 2 * pad_y

            preliminary_scale = avail_w / 900.0
            bw_est = fp.bezel_width * preliminary_scale

            dev_h = avail_h
            scr_h = dev_h - 2 * bw_est
            scr_w = scr_h * video_aspect
            dev_w = scr_w + 2 * bw_est
            if dev_w > avail_w:
                dev_w = avail_w
                scr_w = dev_w - 2 * bw_est
                scr_h = scr_w / video_aspect
                dev_h = scr_h + 2 * bw_est

            scale = dev_w / 900.0
            bw = fp.bezel_width * scale

            scr_x = (W - dev_w) / 2 + bw
            scr_y = (H - dev_h) / 2 + bw

        # Normalize click within the screen rect
        nx = (click_x - scr_x) / max(scr_w, 1)
        ny = (click_y - scr_y) / max(scr_h, 1)

        if nx < 0 or nx > 1 or ny < 0 or ny > 1:
            return -1.0, -1.0

        return nx, ny

    # ── painting ────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # type: ignore[override]
        from ..compositor import compose_scene, draw_empty_bg

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Recording overlay — frozen blurred snapshot + indicator
        if self._recording_mode and self._blurred_frame is not None:
            self._draw_recording_overlay(painter)
            painter.end()
            return

        W, H = float(self.width()), float(self.height())

        # Compute virtual canvas from output dimensions
        canvas_x, canvas_y, canvas_w, canvas_h = self._canvas_rect()
        has_margins = canvas_x > 0.5 or canvas_y > 0.5

        if self._frame is None:
            if has_margins:
                painter.fillRect(QRectF(0, 0, W, H), QColor(0, 0, 0))
            painter.translate(canvas_x, canvas_y)
            draw_empty_bg(painter, canvas_w, canvas_h,
                          bg_preset=self._bg_preset)
            painter.end()
            return

        # Fill margins with black before drawing the canvas
        if has_margins:
            painter.fillRect(QRectF(0, 0, W, H), QColor(0, 0, 0))

        # Render scene at canvas dimensions so the device frame fits
        # properly within the output aspect ratio.
        painter.translate(canvas_x, canvas_y)
        painter.setClipRect(QRectF(0, 0, canvas_w, canvas_h))

        compose_scene(
            painter, self._frame,
            canvas_w, canvas_h,
            self._zoom, self._pan_x, self._pan_y,
            mouse_track=self._mouse_track or None,
            time_ms=self._current_time_ms,
            monitor_rect=self._monitor_rect,
            bg_preset=self._bg_preset,
            frame_preset=self._frame_preset,
            click_events=self._click_events or None,
        )

        painter.setClipping(False)
        painter.resetTransform()

        # Debug overlay: zoom target markers
        if self._debug_overlay and self._debug_keyframes:
            self._draw_debug_overlay(painter)

        painter.end()

    # ── recording overlay helpers ─────────────────────────────────

    def _blur_frame(self, frame: QImage) -> QImage:
        """Apply heavy Gaussian blur to a QImage for the recording overlay."""
        frame = frame.convertToFormat(QImage.Format.Format_RGB888)
        w, h = frame.width(), frame.height()
        bpl = frame.bytesPerLine()
        raw = frame.bits()
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, bpl)
        arr = arr[:, :w * 3].reshape(h, w, 3).copy()
        blurred = cv2.GaussianBlur(arr, (0, 0), sigmaX=30, sigmaY=30)
        qimg = QImage(blurred.data, w, h, w * 3, QImage.Format.Format_RGB888)
        return qimg.copy()

    def _draw_recording_overlay(self, painter: QPainter) -> None:
        """Draw blurred snapshot with a dark overlay and recording indicator."""
        W, H = self.width(), self.height()

        # Draw blurred frame, scaled to widget
        src_w = self._blurred_frame.width()
        src_h = self._blurred_frame.height()
        scale = min(W / src_w, H / src_h)
        dw, dh = int(src_w * scale), int(src_h * scale)
        dx, dy = (W - dw) // 2, (H - dh) // 2
        from PySide6.QtCore import QRect as _QRect
        painter.drawImage(
            _QRect(dx, dy, dw, dh),
            self._blurred_frame,
        )

        # Dark semi-transparent overlay
        painter.fillRect(0, 0, W, H, QColor(0, 0, 0, 120))

        cx, cy = W // 2, H // 2 - 16

        # Pulsing red dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(239, 68, 68))
        painter.drawEllipse(cx - 8, cy - 8, 16, 16)

        # "Recording in progress…"
        font = QFont()
        font.setPixelSize(18)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(0, cy + 20, W, 30, Qt.AlignmentFlag.AlignHCenter, "Recording in progress\u2026")

        # Subtext
        font.setPixelSize(13)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(160, 160, 185))
        painter.drawText(0, cy + 50, W, 24, Qt.AlignmentFlag.AlignHCenter, "Preview paused for better performance")

    # ── debug overlay helpers ───────────────────────────────────────

    def _draw_debug_overlay(self, painter: QPainter) -> None:
        """Draw zoom-target markers only for keyframes active at current time."""
        from ..frames import DEFAULT_FRAME

        if self._frame is None:
            return

        # Use canvas rect so markers align with the compositor output
        cx, cy, W, H = self._canvas_rect()
        iw, ih = self._frame.width(), self._frame.height()
        if iw <= 0 or ih <= 0:
            return

        fp = self._frame_preset or DEFAULT_FRAME
        video_aspect = iw / ih

        # Compute screen rect (same geometry as compositor)
        if fp.is_none:
            if W / H > video_aspect:
                scr_h = H
                scr_w = H * video_aspect
            else:
                scr_w = W
                scr_h = W / video_aspect
            scr_x = (W - scr_w) / 2
            scr_y = (H - scr_h) / 2
        else:
            pad_x = W * fp.padding
            pad_y = H * fp.padding
            avail_w = W - 2 * pad_x
            avail_h = H - 2 * pad_y
            preliminary_scale = avail_w / 900.0
            bw_est = fp.bezel_width * preliminary_scale
            dev_h = avail_h
            scr_h = dev_h - 2 * bw_est
            scr_w = scr_h * video_aspect
            dev_w = scr_w + 2 * bw_est
            if dev_w > avail_w:
                dev_w = avail_w
                scr_w = dev_w - 2 * bw_est
                scr_h = scr_w / video_aspect
                dev_h = scr_h + 2 * bw_est
            scale = dev_w / 900.0
            bw = fp.bezel_width * scale
            scr_x = (W - dev_w) / 2 + bw
            scr_y = (H - dev_h) / 2 + bw

        # Color map by reason type
        def _color_for(kf: ZoomKeyframe) -> QColor:
            r = kf.reason.lower()
            if "mouse" in r:
                return QColor(239, 68, 68, 200)   # red
            elif "typing" in r:
                return QColor(59, 130, 246, 200)   # blue
            elif "click" in r:
                return QColor(250, 204, 21, 200)   # yellow
            else:
                return QColor(168, 85, 247, 200)   # purple (manual/other)

        font = QFont()
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)

        # Reset any zoom transform for debug overlay (draw in canvas coords)
        painter.resetTransform()
        painter.translate(cx, cy)

        # Compute the same focal point the compositor uses for zoom
        zoom = self._zoom
        pan_x = self._pan_x
        pan_y = self._pan_y
        fx = scr_x + pan_x * scr_w
        fy = scr_y + pan_y * scr_h

        t = self._current_time_ms

        # Filter keyframes: only show zoom-in keyframes whose zoom section
        # is currently active.  A section spans from kf.timestamp to the
        # next zoom-out keyframe that follows it.
        sorted_kfs = sorted(self._debug_keyframes, key=lambda k: k.timestamp)
        visible_kfs: list[ZoomKeyframe] = []
        for i, kf in enumerate(sorted_kfs):
            if kf.zoom <= 1.01:
                continue  # skip zoom-out markers
            # Find matching zoom-out (next kf with zoom <= 1.01)
            zoom_out_end = kf.timestamp + 5000  # fallback: 5s window
            for nkf in sorted_kfs[i + 1:]:
                if nkf.zoom <= 1.01:
                    zoom_out_end = nkf.timestamp + nkf.duration
                    break
            # Show if the current time is within this zoom section
            # (include a small margin before to show upcoming zooms)
            if kf.timestamp - 500 <= t <= zoom_out_end:
                visible_kfs.append(kf)

        for kf in visible_kfs:
            color = _color_for(kf)

            # Map keyframe pan position to widget coords, accounting for zoom
            scene_x = scr_x + kf.x * scr_w
            scene_y = scr_y + kf.y * scr_h
            if zoom > 1.001:
                px = (scene_x - fx) * zoom + W / 2
                py = (scene_y - fy) * zoom + H / 2
            else:
                px = scene_x
                py = scene_y

            # Crosshair
            painter.setPen(QPen(color, 2.0))
            arm = 12.0
            painter.drawLine(QPointF(px - arm, py), QPointF(px + arm, py))
            painter.drawLine(QPointF(px, py - arm), QPointF(px, py + arm))

            # Circle around target
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(px, py), 8.0, 8.0)

            # Filled dot at center
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(px, py), 3.0, 3.0)

            # Label
            label = kf.reason or f"{kf.zoom}x"
            time_s = kf.timestamp / 1000.0
            label_text = f"{time_s:.1f}s  {label}"

            # Background pill for label
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(label_text) + 10
            th = fm.height() + 4
            lx = px + 14
            ly = py - th / 2
            # Keep label within widget bounds
            if lx + tw > W:
                lx = px - 14 - tw
            if ly < 0:
                ly = 2
            if ly + th > H:
                ly = H - th - 2

            pill_rect = QRectF(lx, ly, tw, th)
            painter.setPen(Qt.PenStyle.NoPen)
            bg_color = QColor(color)
            bg_color.setAlpha(160)
            painter.setBrush(bg_color)
            painter.drawRoundedRect(pill_rect, 4, 4)

            # Text
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, label_text)

        # Legend in top-left corner (always visible when debug is on)
        painter.resetTransform()
        painter.translate(cx, cy)
        legend_items = [
            (QColor(239, 68, 68), "Mouse burst"),
            (QColor(59, 130, 246), "Typing zone"),
            (QColor(250, 204, 21), "Click cluster"),
        ]
        leg_y = 8.0
        for c, txt in legend_items:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c)
            painter.drawEllipse(QPointF(14, leg_y + 6), 4, 4)
            painter.setPen(QColor(255, 255, 255, 200))
            painter.drawText(QPointF(22, leg_y + 10), txt)
            leg_y += 18

    # ── internal ────────────────────────────────────────────────────

    def _advance_playback(self) -> None:
        if not self._video_cap or not self._video_cap.isOpened():
            self.pause()
            return

        # Compute target playback position from wall-clock elapsed time.
        # This avoids drift caused by QTimer interval rounding and the
        # off-by-one in CAP_PROP_POS_FRAMES (which returns the *next*
        # frame index, not the one just displayed).
        elapsed_s = _time.perf_counter() - self._play_start_wall
        target_ms = self._play_start_pos_ms + elapsed_s * 1000.0

        if target_ms >= self._video_duration_ms:
            self.pause()
            self._playback_pos_ms = self._video_duration_ms
            self._current_time_ms = self._video_duration_ms
            return

        target_frame = self._time_to_frame(target_ms)

        # Only decode a new frame when we actually need one
        if target_frame <= self._last_displayed_frame:
            # No new frame needed yet — just update time
            self._playback_pos_ms = target_ms
            self._current_time_ms = target_ms
            return

        # Read the next frame sequentially.  Seeking via
        # CAP_PROP_POS_FRAMES is unreliable for lossless codecs
        # (huffyuv), so we avoid it during continuous playback and
        # instead read/discard frames to catch up when behind.
        frames_behind = target_frame - self._last_displayed_frame
        if frames_behind > 1:
            skip = min(frames_behind - 1, 8)
            for _ in range(skip):
                if not self._video_cap.grab():
                    break

        ret, frame = self._video_cap.read()
        if not ret:
            # End of actual frames — update time but don't pause
            # until we exceed the authoritative duration
            self._playback_pos_ms = target_ms
            self._current_time_ms = target_ms
            return

        self._last_displayed_frame += frames_behind
        self._playback_pos_ms = target_ms
        self._current_time_ms = target_ms
        self._frame = self._numpy_to_qimage(frame)
        self.update()

    @staticmethod
    def _numpy_to_qimage(frame: np.ndarray) -> QImage:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        return QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()
