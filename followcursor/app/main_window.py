"""Main application window — assembles all widgets and manages state."""

import logging
import os
import subprocess
import uuid
from typing import Optional, List

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, QTimer, QSettings, QByteArray, QEvent, QThread, Signal as CoreSignal
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QStackedWidget,
    QSizePolicy,
    QFrame,
    QApplication,
    QMenu,
    QSystemTrayIcon,
    QMessageBox,
)

from .models import (
    ZoomKeyframe,
    MousePosition,
    KeyEvent,
    ClickEvent,
    RecordingSession,
    DEFAULT_FPS,
    DEFAULT_MOUSE_INTERVAL,
)
from .zoom_engine import ZoomEngine
from .mouse_tracker import MouseTracker
from .keyboard_tracker import KeyboardTracker
from .click_tracker import ClickTracker
from .screen_recorder import ScreenRecorder
from .global_hotkeys import GlobalHotkeys
from .video_exporter import VideoExporter
from .project_file import PROJ_EXT
from .backgrounds import PRESETS as BG_PRESETS
from .frames import FRAME_PRESETS
from .theme import DARK_THEME
from .widgets.title_bar import TitleBar
from .widgets.source_picker import SourcePickerDialog
from .widgets.preview_widget import PreviewWidget
from .widgets.timeline_widget import TimelineWidget
from .widgets.editor_panel import EditorPanel
from .widgets.countdown_overlay import CountdownOverlay
from .widgets.processing_overlay import ProcessingOverlay
from .widgets.recording_border import RecordingBorderOverlay
from .icon import create_app_icon


class _LoadProjectWorker(QThread):
    """Background thread that loads a .fcproj file.

    ZIP extraction and JSON parsing happen here so the GUI thread stays
    responsive and the processing overlay can animate.
    """
    done = CoreSignal(dict)    # the full project dict on success
    failed = CoreSignal(str)   # error message on failure

    def __init__(self, path: str, parent=None) -> None:
        super().__init__(parent)
        self._path = path

    def run(self) -> None:  # noqa: D401
        try:
            from .project_file import load_project
            proj = load_project(self._path)
            self.done.emit(proj)
        except Exception as exc:
            self.failed.emit(str(exc))


class _SaveProjectWorker(QThread):
    """Background thread that writes a .fcproj ZIP file.

    Bundling the AVI can take noticeable time; the GUI thread stays
    responsive while this runs.
    """
    done = CoreSignal(str)     # saved file path on success
    failed = CoreSignal(str)   # error message on failure

    def __init__(self, path: str, video_path: str, session,
                 monitor_rect, actual_fps: float,
                 bg_preset, frame_preset, parent=None) -> None:
        super().__init__(parent)
        self._path = path
        self._video_path = video_path
        self._session = session
        self._monitor_rect = monitor_rect
        self._actual_fps = actual_fps
        self._bg_preset = bg_preset
        self._frame_preset = frame_preset

    def run(self) -> None:  # noqa: D401
        try:
            from .project_file import save_project
            save_project(
                self._path, self._video_path, self._session,
                self._monitor_rect, self._actual_fps,
                self._bg_preset, self._frame_preset,
            )
            self.done.emit(self._path)
        except Exception as exc:
            self.failed.emit(str(exc))


class _FinalizeWorker(QThread):
    """Background thread that performs blocking post-recording cleanup.

    Thread joins, frame-counting, and ffmpeg remux all happen here so the
    GUI thread stays responsive and the processing overlay can animate.
    """
    done = CoreSignal(list, list, list, list, float)  # mouse, keys, clicks, timestamps, fps

    def __init__(
        self,
        recorder: "ScreenRecorder",
        mouse_tracker: "MouseTracker",
        keyboard_tracker: "KeyboardTracker",
        click_tracker: "ClickTracker",
        video_path: str,
        rec_duration_ms: float,
        actual_fps_override: float,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._recorder = recorder
        self._mouse_tracker = mouse_tracker
        self._keyboard_tracker = keyboard_tracker
        self._click_tracker = click_tracker
        self._video_path = video_path
        self._rec_duration_ms = rec_duration_ms
        self._actual_fps_override = actual_fps_override
        self._result_fps: float = actual_fps_override

    def run(self) -> None:  # noqa: D401 — required by QThread
        # These calls may block briefly (capture-thread join, hook-thread joins).
        self._recorder.stop_capture()
        mouse_track = self._mouse_tracker.stop()
        key_events = self._keyboard_tracker.stop()
        click_events = self._click_tracker.stop()
        frame_timestamps = self._recorder.frame_timestamps

        actual_fps = self._actual_fps_override if self._actual_fps_override > 0 else self._recorder.actual_fps
        pipe_frames = self._recorder.frame_count
        logger.info(
            "Recording stopped | duration_ms=%d | backend=%s | actual_fps=%.1f "
            "| pipe_frames=%d | frame_timestamps=%d | output=%s",
            int(self._rec_duration_ms), self._recorder.backend or "unknown",
            actual_fps, pipe_frames, len(frame_timestamps), self._video_path,
        )
        if key_events:
            for i, k in enumerate(key_events):
                logger.debug("Key #%d: ts=%.0fms", i, k.timestamp)
        if click_events:
            for i, c in enumerate(click_events):
                logger.debug("Click #%d: ts=%.0fms  x=%.0f y=%.0f", i, c.timestamp, c.x, c.y)

        # Remux AVI with correct FPS
        self._result_fps = self._remux_with_correct_fps(actual_fps)

        self.done.emit(mouse_track, key_events, click_events, frame_timestamps, self._result_fps)

    # ── remux (runs in worker thread) ───────────────────────────────

    def _remux_with_correct_fps(self, actual_fps: float) -> float:
        """Remux the recorded AVI so its metadata FPS matches reality.

        Returns the correct FPS value.
        """
        if not self._video_path or not os.path.isfile(self._video_path):
            return actual_fps
        if self._rec_duration_ms <= 0:
            return actual_fps

        import cv2 as _cv2

        cap = _cv2.VideoCapture(self._video_path)
        if not cap.isOpened():
            return actual_fps
        real_frames = 0
        while cap.grab():
            real_frames += 1
        old_meta_fps = cap.get(_cv2.CAP_PROP_FPS)
        cap.release()

        if real_frames == 0:
            return actual_fps

        correct_fps = real_frames / (self._rec_duration_ms / 1000.0)

        if old_meta_fps > 0 and abs(correct_fps - old_meta_fps) / old_meta_fps < 0.05:
            logger.info(
                "AVI metadata already correct (meta_fps=%.1f, real_fps=%.2f)",
                old_meta_fps, correct_fps,
            )
            return correct_fps

        try:
            from .utils import ffmpeg_exe, subprocess_kwargs
            ffmpeg = ffmpeg_exe()
        except Exception:
            logger.warning("ffmpeg not found — skipping remux")
            return actual_fps

        temp_output = self._video_path + ".remux.avi"
        cmd = [
            ffmpeg, "-y",
            "-r", f"{correct_fps:.4f}",
            "-i", self._video_path,
            "-c:v", "copy",
            temp_output,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=60,
                **subprocess_kwargs(),
            )
            if result.returncode == 0 and os.path.isfile(temp_output):
                os.replace(temp_output, self._video_path)
                logger.info(
                    "Remuxed AVI: %d frames, fps %.1f → %.2f",
                    real_frames, old_meta_fps, correct_fps,
                )
                return correct_fps
            else:
                stderr = result.stderr.decode(errors="replace")[:300] if result.stderr else ""
                logger.warning("Remux failed (rc=%d): %s", result.returncode, stderr)
        except Exception as exc:
            logger.warning("Remux error: %s", exc)
        finally:
            if os.path.isfile(temp_output):
                try:
                    os.remove(temp_output)
                except OSError:
                    pass
        return actual_fps


class MainWindow(QMainWindow):
    """Central application window — orchestrates recording, editing, and export.

    Manages the full lifecycle: source selection → countdown →
    recording → finalization → editing (zoom, trim, background, frame)
    → export.  Coordinates all worker threads, input trackers, and
    child widgets.  Persists settings (geometry, encoder, presets)
    via ``QSettings``.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FollowCursor")
        self.setWindowIcon(create_app_icon())
        self.setMinimumSize(900, 600)
        self.resize(1200, 800)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(DARK_THEME)

        # ── persistent settings ─────────────────────────────────────
        self._settings = QSettings("FollowCursor", "FollowCursor")
        self._last_export_dir: str = self._settings.value("lastExportDir", "")
        self._last_project_dir: str = self._settings.value("lastProjectDir", "")
        self._restore_geometry()

        # ── core objects ────────────────────────────────────────────
        self._zoom_engine = ZoomEngine()
        self._mouse_tracker = MouseTracker(interval_ms=DEFAULT_MOUSE_INTERVAL, parent=self)
        self._keyboard_tracker = KeyboardTracker(parent=self)
        self._click_tracker = ClickTracker(parent=self)
        self._recorder = ScreenRecorder(parent=self)
        self._hotkeys = GlobalHotkeys(parent=self)
        self._exporter = VideoExporter(parent=self)
        self._border_overlay = RecordingBorderOverlay()

        self._recording = False
        self._selected_monitor: int = 0  # 0 = none selected
        self._monitor_rect: dict = {}    # {left, top, width, height} of selected monitor
        self._source_type: str = "monitor"  # "monitor" | "window"
        self._window_hwnd: int = 0
        self._view: str = "record"  # "record" | "edit"
        self._rec_duration_ms: float = 0
        self._mouse_track: List[MousePosition] = []
        self._key_events: List[KeyEvent] = []
        self._click_events: List[ClickEvent] = []
        self._video_path: str = ""
        self._playback_time: float = 0
        self._actual_fps_override: float = 0.0
        self._frame_timestamps: List[float] = []  # per-frame ms offsets
        self._bg_preset = None  # BackgroundPreset, None = default
        self._frame_preset = None  # FramePreset, None = default
        self._last_export_path: str = ""  # path of last exported file
        self._output_dim = "auto"  # output dimensions: (w, h) or "auto"
        self._trim_start_ms: float = 0.0  # trim start point (0 = beginning)
        self._trim_end_ms: float = 0.0    # trim end point (0 = full duration)
        self._project_path: str = ""      # path to current .fcproj file
        self._unsaved_changes: bool = False  # True when edits exist since last save

        # Restore persisted background & frame presets
        saved_bg = self._settings.value("bgPreset", "")
        if saved_bg:
            match = next((p for p in BG_PRESETS if p.name == saved_bg), None)
            if match:
                self._bg_preset = match
        saved_frame = self._settings.value("framePreset", "")
        if saved_frame:
            match = next((p for p in FRAME_PRESETS if p.name == saved_frame), None)
            if match:
                self._frame_preset = match

        # duration update timer
        self._dur_timer = QTimer(self)
        self._dur_timer.timeout.connect(self._tick_duration)

        # playback zoom sync timer
        self._zoom_sync_timer = QTimer(self)
        self._zoom_sync_timer.setInterval(33)
        self._zoom_sync_timer.timeout.connect(self._sync_zoom)

        # ── build UI ────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # title bar
        self._title_bar = TitleBar(self)
        self._title_bar.export_clicked.connect(self._save_recording)
        root.addWidget(self._title_bar)

        # main content row
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        # sidebar
        sidebar = self._build_sidebar()
        content.addWidget(sidebar)

        # center column
        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(0)

        # recording indicator (hidden by default)
        self._rec_indicator = self._build_rec_indicator()
        self._rec_indicator.setVisible(False)

        # preview area
        preview_area = QWidget()
        preview_area.setObjectName("PreviewArea")
        preview_layout = QVBoxLayout(preview_area)
        preview_layout.setContentsMargins(4, 4, 4, 0)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # recording indicator overlay
        preview_layout.addWidget(self._rec_indicator, 0, Qt.AlignmentFlag.AlignHCenter)

        # placeholder / live preview
        self._placeholder = self._build_placeholder()
        self._preview = PreviewWidget()
        self._preview.setVisible(False)
        self._preview.zoom_at_requested.connect(self._on_preview_zoom_at)
        self._preview.centroid_picked.connect(self._on_centroid_picked)

        # Keyframe whose centroid is being repositioned via preview click
        self._centroid_target_kf_id: str = ""
        self._drag_undo_pushed: bool = False  # debounce undo pushes during drag

        self._preview_stack = QStackedWidget()
        self._preview_stack.addWidget(self._placeholder)
        self._preview_stack.addWidget(self._preview)
        self._preview_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout.addWidget(self._preview_stack, 1)

        center.addWidget(preview_area, 1)

        # control bar
        self._ctrl_bar = self._build_control_bar()
        center.addWidget(self._ctrl_bar)

        # timeline (hidden until edit mode)
        self._timeline = TimelineWidget()
        self._timeline.setVisible(False)
        self._timeline.seek_requested.connect(self._on_seek)
        self._timeline.keyframe_moved.connect(self._on_keyframe_moved)
        self._timeline.segment_clicked.connect(self._on_segment_clicked)
        self._timeline.segment_deleted.connect(self._delete_zoom_section)
        self._timeline.play_pause_clicked.connect(self._on_play_pause)
        self._timeline.click_event_deleted.connect(self._on_click_event_deleted)
        self._timeline.trim_changed.connect(self._on_trim_changed)
        self._timeline.drag_finished.connect(self._on_drag_finished)
        center.addWidget(self._timeline)

        content.addLayout(center, 1)

        # editor panel (hidden until edit mode)
        self._editor = EditorPanel()
        self._editor.setVisible(False)
        self._editor.remove_keyframe.connect(self._on_remove_keyframe)
        self._editor.add_keyframe_at.connect(self._add_keyframe)
        self._editor.auto_keyframes_generated.connect(self._on_auto_keyframes)
        self._editor.background_changed.connect(self._on_bg_changed)
        self._editor.frame_changed.connect(self._on_frame_changed)
        self._editor.debug_overlay_changed.connect(self._on_debug_overlay_changed)
        self._editor.output_dimensions_changed.connect(self._on_output_dim_changed)
        self._editor.undo_requested.connect(self._undo)
        self._editor.redo_requested.connect(self._redo)
        self._editor.encoder_changed.connect(self._on_encoder_changed)
        content.addWidget(self._editor)

        root.addLayout(content, 1)

        # status bar
        self._status_bar = self._build_status_bar()
        root.addWidget(self._status_bar)

        # ── connections ─────────────────────────────────────────────
        self._recorder.frame_ready.connect(self._on_frame)
        self._recorder.recording_finished.connect(self._on_recording_finished)
        self._recorder.capture_backend_changed.connect(self._on_capture_backend_changed)

        self._hotkeys.record_toggle_pressed.connect(self._on_record_toggle)

        self._exporter.progress.connect(self._on_export_progress)
        self._exporter.finished.connect(self._on_export_finished)
        self._exporter.error.connect(self._on_export_error)
        self._exporter.status.connect(self._on_export_status)

        # countdown overlay (covers the central widget)
        self._countdown = CountdownOverlay(central)
        self._countdown.setVisible(False)
        self._countdown.finished.connect(self._do_start_recording)

        # processing overlay (shown while finishing a recording)
        self._processing_overlay = ProcessingOverlay(central)
        self._processing_overlay.setVisible(False)

        # ── system tray icon ────────────────────────────────────────
        self._tray_icon = QSystemTrayIcon(create_app_icon(), self)
        tray_menu = QMenu()
        tray_menu.addAction("Show FollowCursor", self._restore_from_tray)
        tray_menu.addAction("Stop Recording", self._stop_recording)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)

        # Apply persisted background / frame presets to UI
        if self._bg_preset:
            self._preview.set_bg_preset(self._bg_preset)
            self._editor.set_background_by_name(self._bg_preset.name)
        if self._frame_preset:
            self._preview.set_frame_preset(self._frame_preset)
            self._editor.set_frame_by_name(self._frame_preset.name)

        # Restore persisted encoder preference
        saved_encoder = self._settings.value("encoderId", "")
        if saved_encoder:
            self._editor.set_encoder_by_id(saved_encoder)

        # Show encoder in status bar
        self._update_encoder_label(self._editor.encoder_id)

        # Show initial title (Untitled project)
        self._update_title()

        # Register persistent Ctrl+Shift+R hotkey
        self._hotkeys.register_record_hotkey()

    # ════════════════════════════════════════════════════════════════
    #  UI builders
    # ════════════════════════════════════════════════════════════════

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(64)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 8, 0, 12)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Clipchamp-style sidebar: icon + label stacked
        self._btn_record_view = self._make_sidebar_btn("⏺", "Record", active=True)
        self._btn_record_view.clicked.connect(lambda: self._set_view("record"))

        self._btn_edit_view = self._make_sidebar_btn("✎", "Edit")
        self._btn_edit_view.clicked.connect(lambda: self._set_view("edit"))

        sep = QFrame()
        sep.setFixedSize(40, 1)
        sep.setStyleSheet("background-color: #2d2b45;")

        self._btn_load = self._make_sidebar_btn("📂", "Open")
        self._btn_load.clicked.connect(self._load_session)

        self._btn_save = self._make_sidebar_btn("💾", "Save")
        self._btn_save.clicked.connect(self._save_session)

        for w in [self._btn_record_view, self._btn_edit_view, sep, self._btn_load, self._btn_save]:
            layout.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()
        return sidebar

    @staticmethod
    def _make_sidebar_btn(icon: str, label: str, active: bool = False) -> QPushButton:
        btn = QPushButton(f"{icon}\n{label}")
        btn.setObjectName("SidebarBtnActive" if active else "SidebarBtn")
        btn.setToolTip(label)
        return btn

    def _build_rec_indicator(self) -> QWidget:
        w = QWidget()
        w.setObjectName("RecIndicator")
        w.setFixedHeight(36)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(14, 4, 14, 4)
        layout.setSpacing(10)
        dot = QWidget()
        dot.setObjectName("RecDot")
        dot.setFixedSize(10, 10)
        layout.addWidget(dot)
        self._rec_time_label = QLabel("0:00")
        self._rec_time_label.setObjectName("RecTime")
        layout.addWidget(self._rec_time_label)
        return w

    def _build_placeholder(self) -> QWidget:
        w = QWidget()
        w.setObjectName("PlaceholderWidget")
        w.setCursor(Qt.CursorShape.PointingHandCursor)
        w.setMinimumSize(480, 270)
        w.mousePressEvent = lambda e: self._select_source()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(14)
        icon = QLabel("🖥")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 40px; background: transparent;")
        layout.addWidget(icon)
        text = QLabel("Click to select a screen")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setStyleSheet("color: #b0aec4; font-size: 15px; font-weight: 500; background: transparent;")
        layout.addWidget(text)
        hint = QLabel("Choose what you want to record")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        return w

    def _build_control_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("ControlBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 4, 20, 4)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._btn_change_source = QPushButton("🖥  Change Screen")
        self._btn_change_source.setObjectName("CtrlBtn")
        self._btn_change_source.clicked.connect(self._select_source)
        self._btn_change_source.setVisible(False)

        self._btn_record = QPushButton("⏺  Record  (Ctrl+Shift+R)")
        self._btn_record.setObjectName("RecordBtn")
        self._btn_record.clicked.connect(self._start_recording)
        self._btn_record.setVisible(False)

        self._btn_stop = QPushButton("◼  Stop Recording")
        self._btn_stop.setObjectName("StopBtn")
        self._btn_stop.clicked.connect(self._stop_recording)
        self._btn_stop.setVisible(False)

        layout.addWidget(self._btn_change_source)
        layout.addWidget(self._btn_record)
        layout.addWidget(self._btn_stop)

        return bar

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("StatusBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)

        left = QHBoxLayout()
        left.setSpacing(6)
        self._status_dot = QWidget()
        self._status_dot.setObjectName("StatusDotReady")
        self._status_dot.setFixedSize(6, 6)
        left.addWidget(self._status_dot)
        self._status_text = QLabel("Ready")
        self._status_text.setObjectName("StatusLabel")
        self._status_text.setTextFormat(Qt.TextFormat.RichText)
        self._status_text.setOpenExternalLinks(False)
        left.addWidget(self._status_text)
        self._btn_clipchamp = QPushButton("📂  Show in folder")
        self._btn_clipchamp.setObjectName("CtrlBtn")
        self._btn_clipchamp.setVisible(False)
        self._btn_clipchamp.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clipchamp.clicked.connect(self._open_in_clipchamp)
        left.addWidget(self._btn_clipchamp)
        layout.addLayout(left)

        layout.addStretch()

        self._encoder_label = QLabel("")
        self._encoder_label.setObjectName("StatusLabel")
        layout.addWidget(self._encoder_label)

        self._capture_mode_label = QLabel("")
        self._capture_mode_label.setObjectName("StatusLabel")
        self._capture_mode_label.setVisible(False)
        layout.addWidget(self._capture_mode_label)

        right = QLabel("Ctrl+Shift+R  Start / Stop Recording")
        right.setObjectName("StatusLabel")
        layout.addWidget(right)

        return bar

    # ════════════════════════════════════════════════════════════════
    #  Actions
    # ════════════════════════════════════════════════════════════════

    def _select_source(self) -> None:
        """Open the source picker dialog and start capturing the chosen source."""
        dlg = SourcePickerDialog(self, exclude_hwnd=int(self.winId()))
        if dlg.exec():
            source = dlg.chosen_source
            if not source:
                return

            if source.get("type") == "window":
                self._source_type = "window"
                self._window_hwnd = source["hwnd"]
                self._selected_monitor = -1  # sentinel: not a monitor
                self._monitor_rect = {
                    "left": source["left"],
                    "top": source["top"],
                    "width": source["width"],
                    "height": source["height"],
                }
                self._recorder.start_capture_window(source["hwnd"], DEFAULT_FPS)
            else:
                # Monitor source
                self._source_type = "monitor"
                self._selected_monitor = source["index"]
                self._monitor_rect = source
                self._recorder.start_capture(source["index"], DEFAULT_FPS)

            self._preview_stack.setCurrentWidget(self._preview)
            self._preview.setVisible(True)
            self._btn_change_source.setVisible(True)
            self._btn_record.setVisible(True)

    def _start_recording(self) -> None:
        """Initiate recording: show countdown, then begin capture + tracking."""
        if self._selected_monitor == 0 and self._source_type != "window":
            self._select_source()
            return
        # Show countdown overlay, then start recording
        self._btn_record.setVisible(False)
        self._btn_change_source.setVisible(False)
        self._countdown.setGeometry(self.centralWidget().rect())
        self._countdown.start()

    def _do_start_recording(self) -> None:
        """Called when the 3-2-1 countdown finishes."""
        import time as _time

        try:
            self._zoom_engine.clear()
            self._preview.set_recording_mode(True)  # blur + indicator

            # Single shared epoch — recorder + all activity trackers use the
            # exact same origin so every timestamp is perfectly aligned.
            shared_epoch = _time.time()
            shared_start_ms = shared_epoch * 1000
            self._video_path = self._recorder.start_recording(start_time=shared_epoch)
            self._mouse_tracker.start(shared_start_ms)
            self._keyboard_tracker.start(shared_start_ms)
            self._click_tracker.start(shared_start_ms)

            self._recording = True
            self._dur_timer.start(100)
            self._rec_indicator.setVisible(True)
            self._btn_stop.setVisible(True)
            if self._source_type == "monitor" and self._selected_monitor > 0:
                self._border_overlay.show_on_monitor(self._selected_monitor)
            self._status_dot.setObjectName("StatusDotRecording")
            self._status_dot.style().unpolish(self._status_dot)
            self._status_dot.style().polish(self._status_dot)
            self._status_text.setOpenExternalLinks(False)
            self._status_text.setText("Recording")

            source_desc = (
                f"window hwnd={self._window_hwnd}"
                if self._source_type == "window"
                else f"monitor index={self._selected_monitor}"
            )
            backend = self._recorder.backend or "unknown"
            logger.info("Recording started | source=%s | backend=%s | target_fps=%d", source_desc, backend, DEFAULT_FPS)
            logger.info("UI hidden to tray while recording. Press Ctrl+Shift+R to stop.")

            # Minimize to tray so the app is out of the way while recording
            self._minimize_to_tray()
        except Exception:
            logger.exception("Failed to start recording")
            self._recording = False
            self._preview.set_recording_mode(False)
            self._btn_record.setVisible(True)
            self._btn_change_source.setVisible(True)
            self._btn_stop.setVisible(False)
            self._status_text.setOpenExternalLinks(False)
            self._status_text.setText("Recording failed to start")

    def _stop_recording(self) -> None:
        """Stop capturing, launch the finalize worker, and show the processing overlay."""
        if not self._recording:
            return
        self._recording = False
        self._preview.set_recording_mode(False)  # restore normal preview
        self._dur_timer.stop()

        try:
            # Snapshot wall-clock duration and signal recorder to stop writing
            # frames (non-blocking — just toggles a flag).
            self._rec_duration_ms = self._recorder.recording_duration_ms
            self._video_path = self._recorder.stop_recording()
            self._actual_fps_override = self._recorder.actual_fps
        except Exception:
            logger.exception("Error stopping recorder")

        # ── Restore UI immediately so the user sees the app right away ──
        self._border_overlay.hide_border()
        self._rec_indicator.setVisible(False)
        self._btn_stop.setVisible(False)
        self._status_dot.setObjectName("StatusDotReady")
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)
        self._status_text.setOpenExternalLinks(False)
        self._status_text.setText("Finishing recording\u2026")
        self._restore_from_tray()

        # Show prominent processing overlay
        self._processing_overlay.setGeometry(self.centralWidget().rect())
        self._processing_overlay.show_overlay()

        # Defer heavy cleanup (thread joins, video load) so the UI paints
        # before any blocking work happens.
        QTimer.singleShot(50, self._finalize_stop_recording)

    def _finalize_stop_recording(self) -> None:
        """Kick off heavy post-recording work in a background thread."""
        self._finalize_worker = _FinalizeWorker(
            recorder=self._recorder,
            mouse_tracker=self._mouse_tracker,
            keyboard_tracker=self._keyboard_tracker,
            click_tracker=self._click_tracker,
            video_path=self._video_path,
            rec_duration_ms=self._rec_duration_ms,
            actual_fps_override=self._actual_fps_override,
            parent=self,
        )
        self._finalize_worker.done.connect(self._on_finalize_done)
        self._finalize_worker.start()

    def _on_finalize_done(
        self,
        mouse_track: list,
        key_events: list,
        click_events: list,
        frame_timestamps: list,
        actual_fps: float,
    ) -> None:
        """Called on the GUI thread when the finalize worker finishes."""
        try:
            self._mouse_track = mouse_track
            self._key_events = key_events
            self._click_events = click_events
            self._frame_timestamps = frame_timestamps
            self._actual_fps_override = actual_fps

            self._processing_overlay.hide_overlay()
            self._status_text.setText("Ready")
            self._unsaved_changes = True
            self._update_title()
            self._set_view("edit")
        except Exception:
            logger.exception("Error in post-recording finalization")
            self._processing_overlay.hide_overlay()
            self._status_text.setText("Error finalizing recording")

        # Clean up worker reference
        self._finalize_worker.deleteLater()
        self._finalize_worker = None

    def _remux_with_correct_fps(self) -> None:
        """Remux the recorded AVI so its metadata FPS matches reality.

        The recording pipe tells ffmpeg ``-r {target_fps}`` (e.g. 60) but
        WGC only delivers changed frames, so the real write-rate is much
        lower (e.g. 7 fps).  This makes the AVI header claim 60 fps for
        only ~270 frames → OpenCV thinks the video is ~4.5 s instead of
        ~37 s.  Every seek, playback, and export is then wrong.

        This method counts the real frames in the file, computes the
        correct FPS from ``real_frames / (duration_s)``, and remuxes
        (``-c:v copy``) so the container metadata is accurate.
        """
        if not self._video_path or not os.path.isfile(self._video_path):
            return
        if self._rec_duration_ms <= 0:
            return

        import cv2 as _cv2

        # Count real frames — the only reliable method for huffyuv AVI
        cap = _cv2.VideoCapture(self._video_path)
        if not cap.isOpened():
            return
        real_frames = 0
        while cap.grab():
            real_frames += 1
        old_meta_fps = cap.get(_cv2.CAP_PROP_FPS)
        cap.release()

        if real_frames == 0:
            return

        correct_fps = real_frames / (self._rec_duration_ms / 1000.0)

        # Skip remux if metadata is already close enough (within 5 %)
        if old_meta_fps > 0 and abs(correct_fps - old_meta_fps) / old_meta_fps < 0.05:
            logger.info(
                "AVI metadata already correct (meta_fps=%.1f, real_fps=%.2f)",
                old_meta_fps, correct_fps,
            )
            self._actual_fps_override = correct_fps
            return

        try:
            from .utils import ffmpeg_exe, subprocess_kwargs
            ffmpeg = ffmpeg_exe()
        except Exception:
            logger.warning("ffmpeg not found — skipping remux")
            return

        temp_output = self._video_path + ".remux.avi"
        cmd = [
            ffmpeg, "-y",
            "-r", f"{correct_fps:.4f}",
            "-i", self._video_path,
            "-c:v", "copy",
            temp_output,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=60,
                **subprocess_kwargs(),
            )
            if result.returncode == 0 and os.path.isfile(temp_output):
                os.replace(temp_output, self._video_path)
                self._actual_fps_override = correct_fps
                logger.info(
                    "Remuxed AVI: %d frames, fps %.1f → %.2f",
                    real_frames, old_meta_fps, correct_fps,
                )
            else:
                stderr = result.stderr.decode(errors="replace")[:300] if result.stderr else ""
                logger.warning("Remux failed (rc=%d): %s", result.returncode, stderr)
        except Exception as exc:
            logger.warning("Remux error: %s", exc)
        finally:
            if os.path.isfile(temp_output):
                try:
                    os.remove(temp_output)
                except OSError:
                    pass

    def _set_view(self, view: str) -> None:
        """Switch between 'record' and 'edit' views, updating sidebar and widgets."""
        self._view = view

        # sidebar highlight
        self._btn_record_view.setObjectName("SidebarBtnActive" if view == "record" else "SidebarBtn")
        self._btn_record_view.style().unpolish(self._btn_record_view)
        self._btn_record_view.style().polish(self._btn_record_view)
        self._btn_edit_view.setObjectName("SidebarBtnActive" if view == "edit" else "SidebarBtn")
        self._btn_edit_view.style().unpolish(self._btn_edit_view)
        self._btn_edit_view.style().polish(self._btn_edit_view)

        if view == "record":
            self._timeline.setVisible(False)
            self._editor.setVisible(False)
            self._title_bar.set_export_enabled(False)
            if self._selected_monitor:
                self._btn_record.setVisible(True)
                self._btn_change_source.setVisible(True)
            elif self._source_type == "window":
                self._btn_record.setVisible(True)
                self._btn_change_source.setVisible(True)
            # switch back to live capture if a source is selected
            if not self._recorder.is_capturing:
                if self._source_type == "window" and self._window_hwnd:
                    self._recorder.start_capture_window(self._window_hwnd, DEFAULT_FPS)
                    self._preview_stack.setCurrentWidget(self._preview)
                elif self._selected_monitor:
                    self._recorder.start_capture(self._selected_monitor, DEFAULT_FPS)
                    self._preview_stack.setCurrentWidget(self._preview)

        elif view == "edit":
            self._btn_record.setVisible(False)
            self._btn_change_source.setVisible(False)
            self._preview_stack.setCurrentWidget(self._preview)
            self._title_bar.set_export_enabled(bool(self._video_path))
            if self._video_path and os.path.isfile(self._video_path):
                # Use actual recorded FPS so playback speed matches reality
                fps = self._actual_fps_override if self._actual_fps_override > 0 else self._recorder.actual_fps
                # Pass wall-clock duration when available — it is more
                # reliable than OpenCV's CAP_PROP_FRAME_COUNT for
                # lossless codecs (huffyuv).
                dur = self._preview.load_video(
                    self._video_path,
                    actual_fps=fps,
                    duration_ms=self._rec_duration_ms if self._rec_duration_ms > 0 else 0,
                    frame_timestamps=self._frame_timestamps or None,
                )
                # Fall back to video-based duration when the wall-clock
                # value is missing (e.g. loaded from project).
                if dur > 0 and self._rec_duration_ms <= 0:
                    self._rec_duration_ms = dur
            # Provide cursor data for overlay
            self._preview.set_cursor_data(self._mouse_track, self._monitor_rect, self._click_events)
            self._preview.set_current_time(self._playback_time)
            self._timeline.setVisible(self._rec_duration_ms > 0)
            self._editor.setVisible(True)
            self._refresh_editor()
            self._zoom_sync_timer.start()

    # ── title & dirty state ─────────────────────────────────────────

    def _update_title(self) -> None:
        """Refresh the title bar text to reflect project name and save state."""
        name = os.path.basename(self._project_path) if self._project_path else ""
        self._title_bar.set_title(name, self._unsaved_changes)

    def _mark_dirty(self) -> None:
        """Mark the session as having unsaved changes."""
        if not self._unsaved_changes:
            self._unsaved_changes = True
            self._update_title()

    # ── system tray helpers ─────────────────────────────────────────

    def _minimize_to_tray(self) -> None:
        """Hide the window and show a tray icon."""
        self._tray_icon.show()
        self._tray_icon.setToolTip("FollowCursor — Recording… (Ctrl+Shift+R to stop)")
        self.hide()

    def _restore_from_tray(self) -> None:
        """Show the window again and hide the tray icon."""
        self._tray_icon.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Left-click on tray icon — stop recording and restore
            if self._recording:
                self._stop_recording()
            else:
                self._restore_from_tray()

    def _on_record_toggle(self) -> None:
        """Handle Ctrl+Shift+R global hotkey — start or stop recording."""
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _refresh_editor(self) -> None:
        self._editor.refresh(
            self._zoom_engine.keyframes,
            self._mouse_track,
            self._rec_duration_ms,
            self._monitor_rect,
            self._key_events,
            self._click_events,
            self._trim_start_ms,
            self._trim_end_ms,
        )
        self._timeline.set_data(
            self._rec_duration_ms,
            self._playback_time,
            self._zoom_engine.keyframes,
            self._mouse_track,
            self._key_events,
            self._click_events,
            self._trim_start_ms,
            self._trim_end_ms,
        )
        # Keep debug overlay in sync with keyframes
        self._preview.set_debug_keyframes(self._zoom_engine.keyframes)

    def _on_auto_keyframes(self, keyframes) -> None:
        """Handle auto-generated keyframes from activity analysis."""
        # Clear existing and add all generated keyframes
        self._zoom_engine.push_undo()
        self._zoom_engine.clear()
        logger.info("Auto-generate: cleared %d old keyframes, adding %d new",
                     0, len(keyframes))
        for kf in keyframes:
            self._zoom_engine.add_keyframe(kf)
        self._mark_dirty()
        # Update preview at current position
        self._zoom_engine.update(self._playback_time)
        self._preview.set_zoom(
            self._zoom_engine.current_zoom,
            self._zoom_engine.current_pan_x,
            self._zoom_engine.current_pan_y,
        )
        self._refresh_editor()

    def _on_bg_changed(self, preset) -> None:
        """Handle background preset change from editor panel."""
        self._bg_preset = preset
        self._preview.set_bg_preset(preset)

    def _on_frame_changed(self, preset) -> None:
        """Handle device frame preset change from editor panel."""
        self._frame_preset = preset
        self._preview.set_frame_preset(preset)

    def _on_debug_overlay_changed(self, enabled: bool) -> None:
        """Toggle zoom debug overlay on the preview."""
        self._preview.set_debug_overlay(enabled)
        if enabled:
            self._preview.set_debug_keyframes(self._zoom_engine.keyframes)

    def _on_output_dim_changed(self, dim) -> None:
        """Handle output dimension change from editor panel."""
        self._output_dim = dim
        self._preview.set_output_dim(dim)

    def _on_encoder_changed(self, enc_id: str) -> None:
        """Persist the encoder preference and update the status bar."""
        self._settings.setValue("encoderId", enc_id)
        self._update_encoder_label(enc_id)

    def _update_encoder_label(self, enc_id: str) -> None:
        from .utils import encoder_display_name
        self._encoder_label.setText(f"Encoder: {encoder_display_name(enc_id)}")

    # ── undo / redo ─────────────────────────────────────────────────

    def _undo(self) -> None:
        """Undo the last zoom keyframe change."""
        if self._zoom_engine.undo():
            self._zoom_engine.update(self._playback_time)
            self._preview.set_zoom(
                self._zoom_engine.current_zoom,
                self._zoom_engine.current_pan_x,
                self._zoom_engine.current_pan_y,
            )
            self._refresh_editor()

    def _redo(self) -> None:
        """Redo the last undone zoom keyframe change."""
        if self._zoom_engine.redo():
            self._zoom_engine.update(self._playback_time)
            self._preview.set_zoom(
                self._zoom_engine.current_zoom,
                self._zoom_engine.current_pan_x,
                self._zoom_engine.current_pan_y,
            )
            self._refresh_editor()

    # ── trim ────────────────────────────────────────────────────────

    def _on_trim_changed(self, start_ms: float, end_ms: float) -> None:
        """Handle trim handle changes from the timeline."""
        self._trim_start_ms = start_ms
        self._trim_end_ms = end_ms
        self._mark_dirty()

    def _on_drag_finished(self) -> None:
        """Reset undo debounce flag when a timeline drag completes."""
        self._drag_undo_pushed = False
        # Push updated trim bounds to editor so auto-gen uses the trimmed range
        self._editor.refresh(
            self._zoom_engine.keyframes,
            self._mouse_track,
            self._rec_duration_ms,
            self._monitor_rect,
            self._key_events,
            self._click_events,
            self._trim_start_ms,
            self._trim_end_ms,
        )

    # ── recording helpers ───────────────────────────────────────────

    def _tick_duration(self) -> None:
        ms = self._recorder.recording_duration_ms
        s = int(ms / 1000)
        m = s // 60
        self._rec_time_label.setText(f"{m}:{s % 60:02d}")

    def _on_frame(self, frame) -> None:
        if self._view == "record":
            self._preview.set_frame(frame)

    def _on_recording_finished(self, path: str) -> None:
        self._video_path = path

    def _on_capture_backend_changed(self, backend: str) -> None:
        """Update status bar to show which capture backend is active."""
        if backend == "WGC":
            label = "⚡ WGC"
        elif backend == "GDI":
            label = "🖥 GDI"
        else:
            label = f"🖥 {backend}"
        self._capture_mode_label.setText(label)
        self._capture_mode_label.setVisible(True)
        logger.info("Capture backend: %s", backend)

    # ── zoom helpers ────────────────────────────────────────────────

    def _lookup_mouse_pan(self, time_ms: float) -> tuple:
        """Find the recorded mouse position at a given playback time and return
        normalized pan coordinates (0-1).  Falls back to (0.5, 0.5)."""
        if not self._mouse_track or not self._monitor_rect:
            return 0.5, 0.5
        # Binary-ish search: find the sample closest to time_ms
        best = self._mouse_track[0]
        best_delta = abs(best.timestamp - time_ms)
        for mp in self._mouse_track:
            d = abs(mp.timestamp - time_ms)
            if d < best_delta:
                best = mp
                best_delta = d
            elif mp.timestamp > time_ms:
                break
        mon = self._monitor_rect
        px = (best.x - mon.get("left", 0)) / max(mon.get("width", 1), 1)
        py = (best.y - mon.get("top", 0)) / max(mon.get("height", 1), 1)
        return max(0.0, min(1.0, px)), max(0.0, min(1.0, py))

    def _add_keyframe(self, timestamp: float, zoom: float, x: float = -1.0, y: float = -1.0) -> None:
        """Add a zoom keyframe at the given time, with auto zoom-out pairing."""
        # Sentinel -1.0 means "use current playback position"
        if timestamp < 0:
            timestamp = self._playback_time

        # If pan position not specified, look up mouse position at this time
        if x < 0 or y < 0:
            x, y = self._lookup_mouse_pan(timestamp)

        # Prevent overlapping zoom sections: don't add zoom-in if already zoomed
        if zoom > 1.01:
            current_zoom, _, _ = self._zoom_engine.compute_at(timestamp)
            if current_zoom > 1.01:
                return  # already in a zoom section

        self._zoom_engine.push_undo()
        kf = ZoomKeyframe.create(timestamp=timestamp, zoom=zoom, x=x, y=y)
        self._zoom_engine.add_keyframe(kf)
        self._mark_dirty()

        # Auto-add a matching zoom-out keyframe if this is a zoom-in
        # so the zoom doesn't span the entire remaining timeline
        if zoom > 1.01 and not self._recording:
            zoom_out_time = min(timestamp + 3000, self._rec_duration_ms)
            zoom_out_dur = 1200.0  # slower zoom-out for smooth feel

            # Clamp zoom-out so it doesn't overlap the next zoom-in
            next_zoom_in = next(
                (k for k in self._zoom_engine.keyframes
                 if k.timestamp > timestamp and k.zoom > 1.01),
                None,
            )
            if next_zoom_in is not None:
                # End of zoom-out = zoom_out_time + zoom_out_dur
                # Must be ≤ next_zoom_in.timestamp
                boundary = next_zoom_in.timestamp
                if zoom_out_time + zoom_out_dur > boundary:
                    # First try shrinking the duration
                    zoom_out_dur = max(0, boundary - zoom_out_time)
                if zoom_out_time > boundary:
                    # zoom-out start itself exceeds boundary
                    zoom_out_time = max(timestamp + 200, boundary - 200)
                    zoom_out_dur = max(0, boundary - zoom_out_time)

            # Only add if there's no existing zoom-out after this zoom-in
            has_zoom_out = any(
                k.timestamp > timestamp and k.zoom <= 1.01
                for k in self._zoom_engine.keyframes
            )
            if not has_zoom_out:
                kf_out = ZoomKeyframe.create(
                    timestamp=zoom_out_time, zoom=1.0, x=0.5, y=0.5,
                    duration=zoom_out_dur,
                )
                self._zoom_engine.add_keyframe(kf_out)

        if self._recording:
            self._zoom_engine.update(timestamp)
            self._preview.set_zoom(
                self._zoom_engine.current_zoom,
                self._zoom_engine.current_pan_x,
                self._zoom_engine.current_pan_y,
            )
        if self._view == "edit":
            self._zoom_engine.update(self._playback_time)
            self._preview.set_zoom(
                self._zoom_engine.current_zoom,
                self._zoom_engine.current_pan_x,
                self._zoom_engine.current_pan_y,
            )
            self._refresh_editor()

    def _on_remove_keyframe(self, kf_id: str) -> None:
        """Remove a keyframe by ID and refresh the editor."""
        self._zoom_engine.push_undo()
        self._zoom_engine.remove_keyframe(kf_id)
        self._mark_dirty()
        self._zoom_engine.update(self._playback_time)
        self._preview.set_zoom(
            self._zoom_engine.current_zoom,
            self._zoom_engine.current_pan_x,
            self._zoom_engine.current_pan_y,
        )
        self._refresh_editor()

    def _on_keyframe_moved(self, kf_id: str, new_time_ms: float) -> None:
        """Handle dragging a zoom segment edge on the timeline."""
        new_time_ms = max(0.0, min(new_time_ms, self._rec_duration_ms))

        # Find the keyframe being moved and its index
        kfs = self._zoom_engine.keyframes
        moved_idx = None
        for i, kf in enumerate(kfs):
            if kf.id == kf_id:
                moved_idx = i
                break
        if moved_idx is None:
            return

        # Push undo only on the first move of a drag (when timestamp changes)
        moved_kf = kfs[moved_idx]
        if abs(moved_kf.timestamp - new_time_ms) > 0.5:
            # Debounce: only push if we haven't already pushed for this drag
            if not hasattr(self, '_drag_undo_pushed') or not self._drag_undo_pushed:
                self._zoom_engine.push_undo()
                self._drag_undo_pushed = True
            self._mark_dirty()

        # Clamp so it doesn't cross its neighbours
        prev_kf = kfs[moved_idx - 1] if moved_idx > 0 else None
        next_kf = kfs[moved_idx + 1] if moved_idx + 1 < len(kfs) else None

        if prev_kf is not None:
            # Must stay after previous keyframe (+ its transition duration)
            earliest = prev_kf.timestamp + prev_kf.duration
            new_time_ms = max(new_time_ms, earliest)
        if next_kf is not None:
            # Must end before next keyframe starts
            latest = next_kf.timestamp - moved_kf.duration
            new_time_ms = min(new_time_ms, max(0, latest))

        moved_kf.timestamp = new_time_ms
        # Re-sort after timestamp change
        self._zoom_engine.keyframes.sort(key=lambda k: k.timestamp)
        self._zoom_engine.update(self._playback_time)
        self._preview.set_zoom(
            self._zoom_engine.current_zoom,
            self._zoom_engine.current_pan_x,
            self._zoom_engine.current_pan_y,
        )
        self._refresh_editor()

    def _on_segment_clicked(self, start_kf_id: str) -> None:
        """Handle clicking on a zoom segment body — show depth picker + delete."""
        from .widgets.editor_panel import ZOOM_DEPTHS

        # Find the keyframe
        target_kf = None
        for kf in self._zoom_engine.keyframes:
            if kf.id == start_kf_id:
                target_kf = kf
                break
        if target_kf is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58; padding: 4px; }"
            "QMenu::item { padding: 6px 20px; }"
            "QMenu::item:selected { background: #8b5cf6; }"
        )

        for label, level in ZOOM_DEPTHS.items():
            check = " ✓" if abs(target_kf.zoom - level) < 0.01 else ""
            act = menu.addAction(f"{label} ({level}×){check}")
            act.triggered.connect(
                lambda checked, z=level: self._set_segment_zoom(start_kf_id, z)
            )

        menu.addSeparator()

        # Centroid repositioning — click preview to set new center
        centroid_label = f"📍 Set centroid  ({target_kf.x:.2f}, {target_kf.y:.2f})"
        centroid_act = menu.addAction(centroid_label)
        centroid_act.triggered.connect(
            lambda: self._enter_centroid_pick(start_kf_id)
        )

        menu.addSeparator()
        del_act = menu.addAction("🗑 Delete zoom section")
        del_act.triggered.connect(lambda: self._delete_zoom_section(start_kf_id))

        menu.exec(self.cursor().pos())

    def _set_segment_zoom(self, kf_id: str, new_zoom: float) -> None:
        """Update the zoom level of a segment's start keyframe."""
        self._zoom_engine.push_undo()
        self._mark_dirty()
        for kf in self._zoom_engine.keyframes:
            if kf.id == kf_id:
                kf.zoom = new_zoom
                break
        self._zoom_engine.update(self._playback_time)
        self._preview.set_zoom(
            self._zoom_engine.current_zoom,
            self._zoom_engine.current_pan_x,
            self._zoom_engine.current_pan_y,
        )
        self._refresh_editor()

    def _enter_centroid_pick(self, kf_id: str) -> None:
        """Start centroid-pick mode: next preview click sets the keyframe's pan."""
        self._centroid_target_kf_id = kf_id
        self._preview.enter_centroid_pick_mode()

    def _on_centroid_picked(self, pan_x: float, pan_y: float) -> None:
        """Apply the picked centroid to the target keyframe."""
        kf_id = self._centroid_target_kf_id
        self._centroid_target_kf_id = ""
        if not kf_id:
            return
        self._zoom_engine.push_undo()
        for kf in self._zoom_engine.keyframes:
            if kf.id == kf_id:
                kf.x = pan_x
                kf.y = pan_y
                break
        self._mark_dirty()
        self._zoom_engine.update(self._playback_time)
        self._preview.set_zoom(
            self._zoom_engine.current_zoom,
            self._zoom_engine.current_pan_x,
            self._zoom_engine.current_pan_y,
        )
        self._refresh_editor()

    def _delete_zoom_section(self, start_kf_id: str) -> None:
        """Delete a zoom section (the zoom-in keyframe and its matching zoom-out)."""
        # Find the start keyframe's index
        kfs = self._zoom_engine.keyframes
        start_idx = None
        for i, kf in enumerate(kfs):
            if kf.id == start_kf_id:
                start_idx = i
                break
        if start_idx is None:
            return
        self._zoom_engine.push_undo()
        # The zoom-out keyframe is the next one with zoom <= 1.0
        ids_to_remove = [start_kf_id]
        for kf in kfs[start_idx + 1:]:
            if kf.zoom <= 1.01:
                ids_to_remove.append(kf.id)
                break
        for rid in ids_to_remove:
            self._zoom_engine.remove_keyframe(rid)
        self._mark_dirty()
        self._zoom_engine.update(self._playback_time)
        self._preview.set_zoom(
            self._zoom_engine.current_zoom,
            self._zoom_engine.current_pan_x,
            self._zoom_engine.current_pan_y,
        )
        self._refresh_editor()

    def _on_preview_zoom_at(self, time_ms: float, zoom: float, pan_x: float, pan_y: float) -> None:
        """Handle right-click zoom request from preview widget."""
        # Use the editor's depth setting for zoom-in; keep 1.0 for zoom-out
        if zoom > 1.0:
            zoom = self._editor.zoom_level
        self._add_keyframe(time_ms, zoom, pan_x, pan_y)

    # ── playback / timeline ─────────────────────────────────────────

    def _on_seek(self, time_ms: float) -> None:
        self._playback_time = time_ms
        self._preview.seek_to(time_ms)
        self._preview.set_current_time(time_ms)
        self._zoom_engine.update(time_ms)
        self._preview.set_zoom(
            self._zoom_engine.current_zoom,
            self._zoom_engine.current_pan_x,
            self._zoom_engine.current_pan_y,
        )
        self._timeline.set_data(
            self._rec_duration_ms,
            time_ms,
            self._zoom_engine.keyframes,
            self._mouse_track,
            self._key_events,
            self._click_events,
            self._trim_start_ms,
            self._trim_end_ms,
        )

    def _sync_zoom(self) -> None:
        if self._view != "edit":
            self._zoom_sync_timer.stop()
            return
        if self._preview.is_playing:
            t = self._preview.playback_pos_ms
            # Soft-clamp: keep the displayed time within the recording
            # duration so the timer label never exceeds the total, but
            # do NOT force-pause — let the video stop naturally when it
            # runs out of frames.
            if self._rec_duration_ms > 0:
                t = min(t, self._rec_duration_ms)
            self._playback_time = t
            self._zoom_engine.update(t)
            self._preview.set_zoom(
                self._zoom_engine.current_zoom,
                self._zoom_engine.current_pan_x,
                self._zoom_engine.current_pan_y,
            )
            self._timeline.set_data(
                self._rec_duration_ms,
                t,
                self._zoom_engine.keyframes,
                self._mouse_track,
                self._key_events,
                self._click_events,
                self._trim_start_ms,
                self._trim_end_ms,
            )
        else:
            # Preview may have self-paused (end of video) — sync button state
            self._timeline.set_playing(False)

    # ── save / load ─────────────────────────────────────────────────

    def _save_recording(self) -> None:
        """Export the recording as an H.264 MP4 or GIF via the video exporter."""
        if not self._video_path or not os.path.isfile(self._video_path):
            return
        default_name = f"followcursor-{int(self._rec_duration_ms)}.mp4"
        default_path = os.path.join(self._last_export_dir, default_name) if self._last_export_dir else default_name
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Recording",
            default_path,
            "MP4 Video (*.mp4);;GIF Animation (*.gif)",
        )
        if path:
            try:
                # Append the correct extension when the user omitted it
                _is_gif_filter = "gif" in selected_filter.lower()
                if _is_gif_filter and not path.lower().endswith(".gif"):
                    path += ".gif"
                elif not _is_gif_filter and not path.lower().endswith(".mp4"):
                    path += ".mp4"

                self._last_export_dir = os.path.dirname(path)
                self._title_bar.set_export_text("Exporting\u2026")
                self._title_bar.set_export_enabled(False)
                self._status_text.setOpenExternalLinks(False)
                if path.lower().endswith(".gif"):
                    self._status_text.setText("Exporting GIF\u2026")
                else:
                    from .utils import encoder_display_name
                    enc_label = encoder_display_name(self._editor.encoder_id)
                    self._status_text.setText(f"Encoding with {enc_label}\u2026")
                fps = self._recorder.actual_fps
                if self._actual_fps_override > 0:
                    fps = self._actual_fps_override
                self._exporter.export(
                    self._video_path, path,
                    self._zoom_engine.keyframes,
                    fps,
                    self._mouse_track,
                    self._monitor_rect,
                    self._bg_preset,
                    self._frame_preset,
                    self._click_events,
                    self._output_dim,
                    duration_ms=self._rec_duration_ms,
                    frame_timestamps=self._frame_timestamps or None,
                    trim_start_ms=self._trim_start_ms,
                    trim_end_ms=self._trim_end_ms,
                    encoder_id=self._editor.encoder_id,
                )
            except Exception:
                logger.exception("Failed to start export")
                self._title_bar.set_export_text("\u2b06  Export")
                self._title_bar.set_export_enabled(True)
                self._status_text.setText("Export failed to start")

    def _on_play_pause(self) -> None:
        if self._preview.is_playing:
            self._preview.pause()
            self._timeline.set_playing(False)
        else:
            self._preview.play()
            # Only update the button if play actually started
            self._timeline.set_playing(self._preview.is_playing)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        """Handle keyboard shortcuts in edit view."""
        # Ctrl+S — save project (works in any view as long as we have a recording)
        if event.key() == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._save_session()
            return
        if self._view == "edit" and self._rec_duration_ms > 0:
            if event.key() == Qt.Key.Key_Space:
                self._on_play_pause()
                return
            if event.key() == Qt.Key.Key_Z and not event.modifiers():
                zoom = self._editor.zoom_level
                self._add_keyframe(self._playback_time, zoom)
                return
            # Ctrl+Z → undo
            if event.key() == Qt.Key.Key_Z and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self._undo()
                return
            # Ctrl+Shift+Z or Ctrl+Y → redo
            if (event.key() == Qt.Key.Key_Z
                and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)):
                self._redo()
                return
            if event.key() == Qt.Key.Key_Y and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self._redo()
                return
        super().keyPressEvent(event)

    def _on_click_event_deleted(self, index: int) -> None:
        """Delete a click event by index from the timeline."""
        if 0 <= index < len(self._click_events):
            self._click_events.pop(index)
            self._refresh_editor()

    def _on_export_progress(self, pct: float) -> None:
        self._title_bar.set_export_text(f"Exporting {int(pct * 100)}%\u2026")

    def _on_export_finished(self, path: str) -> None:
        self._title_bar.set_export_text("\u2b06  Export")
        self._title_bar.set_export_enabled(True)
        self._last_export_path = path
        name = os.path.basename(path)
        self._status_text.setText(
            f'Saved to <a href="file:///{path.replace(os.sep, "/")}" '
            f'style="color: #a78bfa; text-decoration: underline;">{name}</a>'
        )
        self._status_text.setOpenExternalLinks(True)
        self._btn_clipchamp.setVisible(True)

    def _on_export_status(self, msg: str) -> None:
        """Show encoder status messages (e.g. fallback notifications)."""
        self._status_text.setOpenExternalLinks(False)
        self._status_text.setText(msg)

    def _on_export_error(self, msg: str) -> None:
        self._title_bar.set_export_text("\u2b06  Export")
        self._title_bar.set_export_enabled(True)
        self._status_text.setOpenExternalLinks(False)
        self._status_text.setText(f"Export error: {msg}")
        self._btn_clipchamp.setVisible(False)

    def _open_in_clipchamp(self) -> None:
        """Reveal the exported file in Explorer."""
        import subprocess

        if self._last_export_path and os.path.isfile(self._last_export_path):
            try:
                # /select, highlights the file in Explorer.
                # Path must use backslashes and be quoted for spaces.
                norm = os.path.normpath(self._last_export_path)
                subprocess.Popen(
                    ["explorer.exe", "/select,", norm]
                )
            except Exception:
                # Fallback: open the containing folder
                try:
                    os.startfile(os.path.dirname(self._last_export_path))
                except Exception:
                    pass

    def _save_session(self, save_as: bool = False) -> None:
        """Save the current session as a .fcproj ZIP on a background thread."""
        if not self._video_path or not os.path.isfile(self._video_path):
            return
        session = RecordingSession(
            id=str(uuid.uuid4()),
            start_time=0,
            duration=self._rec_duration_ms,
            mouse_track=self._mouse_track,
            keyframes=list(self._zoom_engine.keyframes),  # snapshot
            key_events=self._key_events,
            click_events=self._click_events,
            frame_timestamps=self._frame_timestamps or None,
            trim_start_ms=self._trim_start_ms,
            trim_end_ms=self._trim_end_ms,
        )
        # Re-use existing path unless Save As or no path yet
        path = self._project_path if self._project_path and not save_as else ""
        if not path:
            default_name = f"followcursor-project{PROJ_EXT}"
            default_path = os.path.join(self._last_project_dir, default_name) if self._last_project_dir else default_name
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Project",
                default_path,
                f"FollowCursor Project (*{PROJ_EXT})",
            )
        if path:
            self._last_project_dir = os.path.dirname(path)
            self._status_text.setOpenExternalLinks(False)
            self._status_text.setText("Saving project\u2026")
            # Run on background thread so the UI stays responsive
            self._save_worker = _SaveProjectWorker(
                path, self._video_path, session,
                self._monitor_rect, self._recorder.actual_fps,
                self._bg_preset, self._frame_preset,
                parent=self,
            )
            self._save_worker.done.connect(self._on_save_done)
            self._save_worker.failed.connect(self._on_save_failed)
            # Optimistically mark unsaved=False so a quick Ctrl+S
            # doesn't trigger a second save while the worker runs.
            self._project_path = path
            self._unsaved_changes = False
            self._update_title()
            self._save_worker.start()

    def _on_save_done(self, path: str) -> None:
        """Background save finished successfully."""
        name = os.path.basename(path)
        self._status_text.setText(
            f'Saved <a href="file:///{path.replace(os.sep, "/")}" '
            f'style="color: #a78bfa; text-decoration: underline;">{name}</a>'
        )
        self._status_text.setOpenExternalLinks(True)

    def _on_save_failed(self, error: str) -> None:
        """Background save failed."""
        self._unsaved_changes = True
        self._update_title()
        self._status_text.setText(f"Save error: {error}")

    def _load_session(self) -> None:
        """Open a .fcproj file and restore the full session on a background thread."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", self._last_project_dir,
            f"FollowCursor Project (*{PROJ_EXT})",
        )
        if not path:
            return
        self._last_project_dir = os.path.dirname(path)
        self._load_project_path = path

        # Show loading overlay
        self._processing_overlay.setGeometry(self.centralWidget().rect())
        self._processing_overlay.show_overlay(
            "Loading project\u2026",
            "Extracting files, please wait",
        )

        # Run in background thread
        self._load_worker = _LoadProjectWorker(path, parent=self)
        self._load_worker.done.connect(self._on_load_done)
        self._load_worker.failed.connect(self._on_load_failed)
        self._load_worker.start()

    def _on_load_done(self, proj: dict) -> None:
        """Called on the GUI thread when the project finishes loading."""
        self._processing_overlay.hide_overlay()
        path = self._load_project_path

        try:
            session = proj["session"]
            self._mouse_track = session.mouse_track
            self._key_events = session.key_events or []
            self._click_events = session.click_events or []
            self._rec_duration_ms = session.duration
            self._zoom_engine.clear()
            for kf in session.keyframes:
                self._zoom_engine.add_keyframe(kf)
            if proj["video_path"]:
                self._video_path = proj["video_path"]
            if proj["monitor_rect"]:
                self._monitor_rect = proj["monitor_rect"]
            self._actual_fps_override = proj.get("actual_fps", 30.0)
            self._frame_timestamps = session.frame_timestamps or []
            self._trim_start_ms = session.trim_start_ms
            self._trim_end_ms = session.trim_end_ms

            # Restore background preset if saved
            loaded_bg = proj.get("bg_preset")
            if loaded_bg:
                self._bg_preset = loaded_bg
                self._preview.set_bg_preset(loaded_bg)

            # Restore frame preset if saved
            loaded_frame = proj.get("frame_preset")
            if loaded_frame:
                self._frame_preset = loaded_frame
                self._preview.set_frame_preset(loaded_frame)

            self._set_view("edit")
            self._project_path = path
            self._unsaved_changes = False
            self._update_title()
            name = os.path.basename(path)
            self._status_text.setOpenExternalLinks(False)
            self._status_text.setText(f"Loaded {name}")
        except Exception as exc:
            self._status_text.setOpenExternalLinks(False)
            self._status_text.setText(f"Load error: {exc}")

        # Clean up worker reference
        self._load_worker.deleteLater()
        self._load_worker = None

    def _on_load_failed(self, error: str) -> None:
        """Called on the GUI thread when project loading fails."""
        self._processing_overlay.hide_overlay()
        self._status_text.setOpenExternalLinks(False)
        self._status_text.setText(f"Load error: {error}")
        self._load_worker.deleteLater()
        self._load_worker = None

    # ── cleanup ─────────────────────────────────────────────────────

    def changeEvent(self, event) -> None:  # type: ignore[override]
        """Handle DPI / screen change so fonts and geometry stay correct."""
        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.ScreenChangeInternal,
            QEvent.Type.WindowStateChange,
        ):
            # Re-apply stylesheet so font-size values are recalculated for new DPI
            QTimer.singleShot(0, lambda: self.setStyleSheet(DARK_THEME))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Handle window close — prompt to save, persist settings, clean up."""
        # ── Unsaved-changes confirmation ────────────────────────────
        if self._unsaved_changes and self._video_path:
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Unsaved Changes")
            dlg.setText("You have unsaved changes. Do you want to save before closing?")
            dlg.setIcon(QMessageBox.Icon.Warning)
            btn_save = dlg.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
            dlg.addButton("Don\u2019t Save", QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = dlg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            dlg.setDefaultButton(btn_cancel)
            dlg.exec()
            clicked = dlg.clickedButton()
            if clicked == btn_cancel:
                event.ignore()
                return
            if clicked == btn_save:
                self._save_session()
                # If user cancelled the save dialog, don't close
                if self._unsaved_changes:
                    event.ignore()
                    return

        # Persist window geometry and settings
        self._settings.setValue("windowGeometry", self.saveGeometry())
        self._settings.setValue("lastExportDir", self._last_export_dir)
        self._settings.setValue("lastProjectDir", self._last_project_dir)
        if self._bg_preset:
            self._settings.setValue("bgPreset", self._bg_preset.name)
        if self._frame_preset:
            self._settings.setValue("framePreset", self._frame_preset.name)
        self._settings.sync()

        self._hotkeys.unregister_record_hotkey()
        self._recorder.stop_capture()
        self._mouse_tracker.stop()
        self._keyboard_tracker.stop()
        self._click_tracker.stop()
        self._zoom_sync_timer.stop()
        self._dur_timer.stop()
        self._border_overlay.hide_border()

        # Close any open child dialogs/windows so they don't keep the app alive
        for w in QApplication.topLevelWidgets():
            if w is not self:
                w.close()

        event.accept()
        # Force quit — ensures the process exits even with leftover threads
        import os
        os._exit(0)

    def _restore_geometry(self) -> None:
        """Restore window size/position from saved settings."""
        geom = self._settings.value("windowGeometry")
        if geom and isinstance(geom, QByteArray):
            self.restoreGeometry(geom)
