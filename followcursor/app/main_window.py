"""Main application window — assembles all widgets and manages state."""

import logging
import os
import subprocess
import threading
import uuid
from typing import Optional, List

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, QTimer, QSettings, QByteArray, QEvent, QThread, Signal as CoreSignal, QSize
from PySide6.QtGui import QIcon
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
    QDialog,
    QToolButton,
)

from .models import (
    ZoomKeyframe,
    MousePosition,
    KeyEvent,
    ClickEvent,
    VideoSegment,
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
# VideoExporter imported lazily to avoid pulling in cv2/numpy at startup
from .project_file import PROJ_EXT
from .backgrounds import PRESETS as BG_PRESETS
from .frames import FRAME_PRESETS
from .theme import DARK_THEME
from .fluent_effects import apply_shadow, install_focus_ring
from .widgets.title_bar import TitleBar
from .widgets.source_picker import SourcePickerDialog
from .widgets.preview_widget import PreviewWidget
from .widgets.timeline_widget import TimelineWidget
from .widgets.editor_panel import EditorPanel
from .widgets.countdown_overlay import CountdownOverlay
from .widgets.processing_overlay import ProcessingOverlay
from .widgets.recording_border import RecordingBorderOverlay
from .icon import create_app_icon
from .icon_loader import load_icon
from . import tokens as T
from .mica import is_mica_supported, enable_mica


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

    Bundling the video can take noticeable time; the GUI thread stays
    responsive while this runs.  When *metadata_only* is True, only
    the JSON metadata is rewritten — the existing video entry is
    carried over byte-for-byte from the old ZIP.
    """
    done = CoreSignal(str)     # saved file path on success
    failed = CoreSignal(str)   # error message on failure

    def __init__(self, path: str, video_path: str, session,
                 monitor_rect, actual_fps: float,
                 bg_preset, frame_preset, click_preset,
                 keystroke_config,
                 annotations,
                 metadata_only: bool = False,
                 parent=None) -> None:
        super().__init__(parent)
        self._path = path
        self._video_path = video_path
        self._session = session
        self._monitor_rect = monitor_rect
        self._actual_fps = actual_fps
        self._bg_preset = bg_preset
        self._frame_preset = frame_preset
        self._click_preset = click_preset
        self._keystroke_config = keystroke_config
        self._annotations = annotations
        self._metadata_only = metadata_only

    def run(self) -> None:  # noqa: D401
        try:
            from .project_file import save_project
            save_project(
                self._path, self._video_path, self._session,
                self._monitor_rect, self._actual_fps,
                self._bg_preset, self._frame_preset,
                self._click_preset, self._keystroke_config,
                self._annotations,
                metadata_only=self._metadata_only,
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
        mouse_positions: list,
        keyboard_tracker: "KeyboardTracker",
        click_tracker: "ClickTracker",
        video_path: str,
        rec_duration_ms: float,
        actual_fps_override: float,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._recorder = recorder
        self._mouse_positions = mouse_positions
        self._keyboard_tracker = keyboard_tracker
        self._click_tracker = click_tracker
        self._video_path = video_path
        self._rec_duration_ms = rec_duration_ms
        self._actual_fps_override = actual_fps_override
        self._result_fps: float = actual_fps_override

    def run(self) -> None:  # noqa: D401 — required by QThread
        # These calls may block briefly (capture-thread join, hook-thread joins).
        self._recorder.stop_capture()
        mouse_track = self._mouse_positions  # already stopped on main thread
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
        """Remux the recording so its metadata FPS matches reality.

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
                "Video metadata already correct (meta_fps=%.1f, real_fps=%.2f)",
                old_meta_fps, correct_fps,
            )
            return correct_fps

        try:
            from .utils import ffmpeg_exe, subprocess_kwargs
            ffmpeg = ffmpeg_exe()
        except Exception:
            logger.warning("ffmpeg not found — skipping remux")
            return actual_fps

        temp_output = self._video_path + ".remux.mp4"
        cmd = [
            ffmpeg, "-y",
            "-r", f"{correct_fps:.4f}",
            "-i", self._video_path,
            "-c:v", "copy",
            temp_output,
        ]
        # Scale timeout with recording length; -c:v copy is fast but large
        # files on slow storage can exceed the old 60 s default.
        remux_timeout = max(120, int(self._rec_duration_ms / 1000) + 30)
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=remux_timeout,
                **subprocess_kwargs(),
            )
            if result.returncode == 0 and os.path.isfile(temp_output):
                os.replace(temp_output, self._video_path)
                logger.info(
                    "Remuxed video: %d frames, fps %.1f → %.2f",
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


class _PreviewSynthWorker(QThread):
    """Background thread for voiceover preview TTS synthesis.

    Uses the same ``_build_speech_config`` helper as the final synthesis
    path so voice resolution is identical (region vs endpoint).
    """
    done = CoreSignal(str)    # output audio path
    error = CoreSignal(str)   # error message

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        voice: str,
        text: str,
        output_path: str,
        rate: float,
        volume: float,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._endpoint = endpoint
        self._api_key = api_key
        self._voice = voice
        self._text = text
        self._output_path = output_path
        self._rate = rate
        self._volume = volume

    def run(self) -> None:  # noqa: D401
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            self.error.emit("azure-cognitiveservices-speech not installed.")
            return

        try:
            from .ai_service import _build_speech_config
            speech_config = _build_speech_config(self._api_key, self._endpoint)
            speech_config.speech_synthesis_voice_name = self._voice

            audio_config = speechsdk.audio.AudioOutputConfig(
                filename=self._output_path
            )
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=audio_config,
            )

            use_ssml = (
                abs(self._rate - 1.0) > 0.05 or abs(self._volume - 1.0) > 0.05
            )
            if use_ssml:
                import html as _html
                rate_str = f"{int((self._rate - 1.0) * 100):+d}%"
                vol_str = f"{int((self._volume - 1.0) * 100):+d}%"
                ssml = (
                    '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
                    f'<voice name="{_html.escape(self._voice)}">'
                    f'<prosody rate="{rate_str}" volume="{vol_str}">'
                    f'{_html.escape(self._text)}'
                    '</prosody></voice></speak>'
                )
                result = synthesizer.speak_ssml_async(ssml).get()
            else:
                result = synthesizer.speak_text_async(self._text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                self.done.emit(self._output_path)
            elif result.reason == speechsdk.ResultReason.Canceled:
                details = result.cancellation_details
                err = (
                    str(details.error_details)[:150]
                    if details.error_details
                    else str(details.reason)
                )
                self.error.emit(f"Error: {err}")
            else:
                self.error.emit(f"Unexpected: {result.reason}")
        except Exception as exc:
            self.error.emit(f"Error: {str(exc)[:150]}")


class _VoiceoverDialog(QDialog):
    """Dialog for creating or editing a voiceover segment.

    Proper QDialog with text edit, voice picker, and action buttons.
    Buttons: Preview | OK | Cancel (+ Delete in edit mode).
    """

    RESULT_OK = 1
    RESULT_DELETE = 2
    RESULT_PREVIEW = 3

    def __init__(
        self,
        timestamp_ms: float,
        voice: str,
        text: str = "",
        title: str = "Add Voiceover",
        is_edit: bool = False,
        rate: float = 1.0,
        volume: float = 1.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)

        self._timestamp_ms = timestamp_ms
        self._result_code = 0
        self._init_rate = rate
        self._init_volume = volume

        _DLG_STYLE = (
            "background: #1b1a2e; color: #e4e4ed;"
        )
        _BTN_STYLE = (
            "QPushButton { min-width: 80px; min-height: 28px;"
            "  background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58;"
            "  border-radius: 6px; padding: 4px 16px; font-size: 13px; }"
            "QPushButton:hover { background: #8b5cf6; }"
        )

        self.setStyleSheet(_DLG_STYLE)

        from PySide6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QComboBox, QPushButton,
        )

        self._preview_btn = None  # stored for enable/disable
        self._status_label = None
        self._preview_audio_path: str = ""  # cached audio from last preview
        self._preview_text: str = ""  # text that was previewed
        self._preview_voice: str = ""  # voice that was previewed
        self._preview_rate: float = 1.0
        self._preview_volume: float = 1.0

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Header
        t_str = f"{int(timestamp_ms / 1000) // 60}:{int(timestamp_ms / 1000) % 60:02d}"
        header = QLabel(f"Voiceover at <b>{t_str}</b>")
        header.setStyleSheet("font-size: 15px; color: #e4e4ed;")
        layout.addWidget(header)

        desc = QLabel("Enter voiceover text and pick a voice.")
        desc.setStyleSheet("font-size: 12px; color: #9c99b6;")
        layout.addWidget(desc)

        # Text edit
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText("Type your voiceover text here\u2026")
        self._text_edit.setPlainText(text)
        self._text_edit.setFixedHeight(100)
        self._text_edit.setStyleSheet(
            "QTextEdit { background: #201f34; color: #e4e4ed; border: 1px solid #3d3a58;"
            "  border-radius: 6px; padding: 6px; font-size: 13px; }"
        )
        layout.addWidget(self._text_edit)

        # Voice picker
        voice_row = QHBoxLayout()
        voice_row.setSpacing(8)
        voice_label = QLabel("Voice:")
        voice_label.setStyleSheet("color: #9c99b6; font-size: 13px;")
        voice_row.addWidget(voice_label)
        self._voice_combo = QComboBox()
        self._voice_combo.setEditable(True)
        from .widgets.editor_panel import _cached_voices
        if _cached_voices:
            for v in _cached_voices:
                self._voice_combo.addItem(v)
        else:
            self._voice_combo.addItem("en-US-Ava:DragonHDLatestNeural")
            self._voice_combo.addItem("en-US-Andrew:DragonHDLatestNeural")
        self._voice_combo.setCurrentText(voice)
        self._voice_combo.setStyleSheet(
            "QComboBox { background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58;"
            "  border-radius: 6px; padding: 4px 8px; font-size: 13px; }"
        )
        voice_row.addWidget(self._voice_combo, 1)
        layout.addLayout(voice_row)

        # Rate slider
        from PySide6.QtWidgets import QSlider
        rate_row = QHBoxLayout()
        rate_row.setSpacing(8)
        rate_label = QLabel("Rate:")
        rate_label.setStyleSheet("color: #9c99b6; font-size: 13px;")
        rate_row.addWidget(rate_label)
        self._rate_slider = QSlider(Qt.Orientation.Horizontal)
        self._rate_slider.setRange(0, 300)  # 0.0x to 3.0x (in hundredths)
        self._rate_slider.setValue(int(getattr(self, '_init_rate', 1.0) * 100))
        self._rate_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: #201f34; height: 4px; border-radius: 2px; }"
            "QSlider::handle:horizontal { background: #8b5cf6; width: 14px; margin: -5px 0; border-radius: 7px; }"
        )
        rate_row.addWidget(self._rate_slider, 1)
        self._rate_value = QLabel(f"{self._rate_slider.value() / 100:.1f}x")
        self._rate_value.setFixedWidth(36)
        self._rate_value.setStyleSheet("color: #9c99b6; font-size: 12px;")
        self._rate_slider.valueChanged.connect(lambda v: self._rate_value.setText(f"{v / 100:.1f}x"))
        rate_row.addWidget(self._rate_value)
        layout.addLayout(rate_row)

        # Volume slider
        vol_row = QHBoxLayout()
        vol_row.setSpacing(8)
        vol_label = QLabel("Volume:")
        vol_label.setStyleSheet("color: #9c99b6; font-size: 13px;")
        vol_row.addWidget(vol_label)
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 300)  # 0.0x to 3.0x (in hundredths)
        self._vol_slider.setValue(int(getattr(self, '_init_volume', 1.0) * 100))
        self._vol_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: #201f34; height: 4px; border-radius: 2px; }"
            "QSlider::handle:horizontal { background: #8b5cf6; width: 14px; margin: -5px 0; border-radius: 7px; }"
        )
        vol_row.addWidget(self._vol_slider, 1)
        self._vol_value = QLabel(f"{self._vol_slider.value() / 100:.1f}x")
        self._vol_value.setFixedWidth(36)
        self._vol_value.setStyleSheet("color: #9c99b6; font-size: 12px;")
        self._vol_slider.valueChanged.connect(lambda v: self._vol_value.setText(f"{v / 100:.1f}x"))
        vol_row.addWidget(self._vol_value)
        layout.addLayout(vol_row)

        # Status label + progress bar (for preview feedback)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #9c99b6; font-size: 12px;")
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        from PySide6.QtWidgets import QProgressBar
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { background: #201f34; border: none; border-radius: 2px; }"
            "QProgressBar::chunk { background: #8b5cf6; border-radius: 2px; }"
        )
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._preview_btn = QPushButton("\u25b6 Preview")
        self._preview_btn.setStyleSheet(_BTN_STYLE)
        self._preview_btn.clicked.connect(self._on_preview)
        btn_row.addWidget(self._preview_btn)

        if is_edit:
            btn_delete = QPushButton("Delete")
            btn_delete.setStyleSheet(
                _BTN_STYLE.replace("#28263e", "#7f1d1d").replace("#3d3a58", "#991b1b")
            )
            btn_delete.clicked.connect(lambda: self._finish(self.RESULT_DELETE))
            btn_row.addWidget(btn_delete)

        btn_ok = QPushButton("OK")
        btn_ok.setStyleSheet(
            _BTN_STYLE.replace("#28263e", "#8b5cf6").replace("#3d3a58", "#7c3aed")
        )
        btn_ok.clicked.connect(lambda: self._finish(self.RESULT_OK))
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(_BTN_STYLE)
        btn_cancel.clicked.connect(lambda: self._finish(0))
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    def _on_preview(self) -> None:
        """Synthesize and play TTS in-place without closing the dialog."""
        text = self._text_edit.toPlainText().strip()
        if not text:
            self._status_label.setText("Enter voiceover text first.")
            self._status_label.setVisible(True)
            return

        # Load AI settings for endpoint + key
        from PySide6.QtCore import QSettings
        from .credentials import unprotect
        settings = QSettings("FollowCursor", "FollowCursor")
        endpoint = settings.value("ai/endpoint", "")
        api_key = unprotect(settings.value("ai/apiKey", ""))
        if not endpoint or not api_key:
            self._status_label.setText("Configure AI Settings first (endpoint + API key).")
            self._status_label.setVisible(True)
            return

        # Stop any currently playing preview audio
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

        self._preview_btn.setEnabled(False)
        self._status_label.setText("Generating speech\u2026")
        self._status_label.setVisible(True)
        self._progress.setVisible(True)

        voice = self._voice_combo.currentText().strip()
        rate = self._rate_slider.value() / 100.0
        vol = self._vol_slider.value() / 100.0

        # Run synthesis in a background thread to keep the dialog responsive.
        # Uses _build_speech_config from ai_service so the same region-based
        # config is used as in the final "Add" path (avoids voice mismatch).
        import tempfile
        output_path = os.path.join(
            tempfile.gettempdir(), "followcursor_vo_preview.wav"
        )

        self._synth_worker = _PreviewSynthWorker(
            endpoint, api_key, voice, text, output_path, rate, vol, parent=self,
        )
        self._synth_worker.done.connect(self._on_preview_synth_done)
        self._synth_worker.error.connect(self._on_preview_synth_error)
        self._synth_worker.finished.connect(self._synth_worker.deleteLater)
        self._synth_worker.start()

    def _on_preview_synth_done(self, output_path: str) -> None:
        """Handle successful TTS synthesis — play the audio."""
        voice = self._voice_combo.currentText().strip()
        text = self._text_edit.toPlainText().strip()
        rate = self._rate_slider.value() / 100.0
        vol = self._vol_slider.value() / 100.0

        self._preview_audio_path = output_path
        self._preview_text = text
        self._preview_voice = voice
        self._preview_rate = rate
        self._preview_volume = vol

        self._status_label.setText("Playing\u2026")
        self._progress.setVisible(False)
        self._preview_btn.setEnabled(True)

        # Play asynchronously so the dialog stays responsive
        import winsound
        winsound.PlaySound(
            output_path,
            winsound.SND_FILENAME | winsound.SND_NODEFAULT | winsound.SND_ASYNC,
        )
        self._status_label.setText("\u2713 Preview complete.")

    def _on_preview_synth_error(self, msg: str) -> None:
        """Handle TTS synthesis failure."""
        self._status_label.setText(msg)
        self._preview_btn.setEnabled(True)
        self._progress.setVisible(False)

    def _finish(self, code: int) -> None:
        self._result_code = code
        self.close()

    def exec(self) -> int:
        super().exec()
        return self._result_code

    def closeEvent(self, event) -> None:
        """Accept close without propagating to parent."""
        event.accept()

    @property
    def cached_audio_path(self) -> str:
        """Return the cached audio path if text, voice, rate, volume match the last preview."""
        if (
            self._preview_audio_path
            and os.path.isfile(self._preview_audio_path)
            and self._text_edit.toPlainText().strip() == self._preview_text
            and self._voice_combo.currentText().strip() == self._preview_voice
            and self.rate == self._preview_rate
            and self.volume == self._preview_volume
        ):
            return self._preview_audio_path
        return ""

    @property
    def text(self) -> str:
        return self._text_edit.toPlainText().strip()

    @property
    def voice(self) -> str:
        return self._voice_combo.currentText()

    @property
    def rate(self) -> float:
        return self._rate_slider.value() / 100.0

    @property
    def volume(self) -> float:
        return self._vol_slider.value() / 100.0

    @property
    def timestamp_ms(self) -> float:
        return self._timestamp_ms


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
        
        # Enable Mica backdrop on Windows 11 Build 22621+
        hwnd = int(self.winId())
        if is_mica_supported():
            success = enable_mica(hwnd, dark_mode=True)
            if success:
                # Set transparent background for Mica to be visible
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                logger.info("Mica backdrop enabled with transparent background")

                def _apply_mica_transparency():
                    self.setObjectName("micaHostWindow")
                    central = self.centralWidget()
                    if central:
                        central.setObjectName("micaCentralWidget")
                    extra = (
                        "QMainWindow#micaHostWindow { background-color: transparent; } "
                        "QWidget#micaCentralWidget { background-color: transparent; }"
                    )
                    self.setStyleSheet(self.styleSheet() + extra)

                QTimer.singleShot(0, _apply_mica_transparency)

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
        self._exporter = None  # Created lazily via _ensure_exporter()
        self._border_overlay = RecordingBorderOverlay()
        self._ai_worker = None   # AIWorker, created lazily
        self._voiceover_segments: list = []  # List[VoiceoverSegment]
        self._video_segments: List[VideoSegment] = []  # timeline video segments
        self._vo_played_ids: set = set()  # track which voiceovers have played this playback
        self._vo_lock = threading.Lock()  # protect _vo_played_ids access

        self._recording = False
        self._selected_monitor: int = 0  # 0 = none selected
        self._monitor_rect: dict = {}    # {left, top, width, height} of selected monitor
        self._source_type: str = "monitor"  # "monitor" | "window"
        self._window_hwnd: int = 0
        self._view: str = "record"  # "record" | "edit"
        self._rec_duration_ms: float = 0
        self._mouse_track: List[MousePosition] = []
        self._mouse_track_timestamps: List[float] = []
        self._key_events: List[KeyEvent] = []
        self._click_events: List[ClickEvent] = []
        self._video_path: str = ""
        self._playback_time: float = 0
        self._actual_fps_override: float = 0.0
        self._frame_timestamps: List[float] = []  # per-frame ms offsets
        self._bg_preset = None  # BackgroundPreset, None = default
        self._frame_preset = None  # FramePreset, None = default
        self._click_preset = None  # ClickEffectPreset, None = default
        self._last_export_path: str = ""  # path of last exported file
        self._output_dim = "auto"  # output dimensions: (w, h) or "auto"
        self._trim_start_ms: float = 0.0  # trim start point (0 = beginning)
        self._trim_end_ms: float = 0.0    # trim end point (0 = full duration)
        self._project_path: str = ""      # path to current .fcproj file
        self._unsaved_changes: bool = False  # True when edits exist since last save
        self._keystroke_config = None  # KeystrokeOverlayConfig or None
        self._annotations = None  # AnnotationCollection or None
        self._chapters: list = []  # List[Chapter]

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
        # Restore persisted click effect preset
        from .models import CLICK_EFFECT_PRESETS
        saved_click = self._settings.value("clickPreset", "")
        if saved_click:
            match = next((p for p in CLICK_EFFECT_PRESETS if p.name == saved_click), None)
            if match:
                self._click_preset = match

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
        self._title_bar.discard_clicked.connect(self._discard_recording)
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
        self._preview.pan_point_requested.connect(self._on_preview_pan_point)
        self._preview.centroid_picked.connect(self._on_centroid_picked)
        self._preview.centroid_dragged.connect(self._on_centroid_dragged)

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
        self._timeline.pan_point_clicked.connect(self._on_pan_point_clicked)
        self._timeline.play_pause_clicked.connect(self._on_play_pause)
        self._timeline.click_event_deleted.connect(self._on_click_event_deleted)
        self._timeline.add_zoom_requested.connect(
            lambda t: self._add_keyframe(t, self._editor.zoom_level)
        )
        self._timeline.add_voiceover_requested.connect(
            lambda t: self._on_add_voiceover_requested(t, self._editor.selected_voice)
        )
        self._timeline.voiceover_clicked.connect(self._on_voiceover_clicked)
        self._timeline.voiceover_deleted.connect(self._on_voiceover_deleted)
        self._timeline.voiceover_moved.connect(self._on_voiceover_moved)
        self._timeline.video_segment_deleted.connect(self._on_video_segment_deleted)
        self._timeline.split_requested.connect(self._split_at_time)
        self._timeline.trim_changed.connect(self._on_trim_changed)
        self._timeline.trim_reset.connect(self._on_trim_reset)
        self._timeline.drag_finished.connect(self._on_drag_finished)
        center.addWidget(self._timeline)

        content.addLayout(center, 1)

        # editor panel (hidden until edit mode)
        self._editor = EditorPanel()
        self._editor.setVisible(False)
        apply_shadow(self._editor, level="subtle")  # Fluent 2 panel elevation
        self._editor.remove_keyframe.connect(self._on_remove_keyframe)
        self._editor.add_keyframe_at.connect(self._add_keyframe)
        self._editor.auto_keyframes_generated.connect(self._on_auto_keyframes)
        self._editor.background_changed.connect(self._on_bg_changed)
        self._editor.frame_changed.connect(self._on_frame_changed)
        self._editor.click_effect_changed.connect(self._on_click_changed)
        self._editor.keystroke_config_changed.connect(self._on_keystroke_config_changed)
        self._editor.annotation_added.connect(self._on_annotation_added)
        self._editor.annotation_removed.connect(self._on_annotation_removed)
        self._editor.annotation_updated.connect(self._on_annotation_updated)
        self._editor.auto_detect_chapters_requested.connect(self._on_auto_detect_chapters)
        self._editor.chapter_added.connect(self._on_chapter_added)
        self._editor.chapter_removed.connect(self._on_chapter_removed)
        self._editor.debug_overlay_changed.connect(self._on_debug_overlay_changed)
        self._editor.output_dimensions_changed.connect(self._on_output_dim_changed)
        self._editor.undo_requested.connect(self._undo)
        self._editor.redo_requested.connect(self._redo)
        self._editor.encoder_changed.connect(self._on_encoder_changed)
        self._editor.ai_zoom_requested.connect(self._on_ai_zoom_requested)
        self._editor.add_voiceover_requested.connect(self._on_add_voiceover_requested)
        content.addWidget(self._editor)

        # Enable zoom debug overlay by default
        self._preview.set_debug_overlay(False)

        root.addLayout(content, 1)

        # status bar
        self._status_bar = self._build_status_bar()
        root.addWidget(self._status_bar)

        # ── connections ─────────────────────────────────────────────
        self._recorder.frame_ready.connect(self._on_frame)
        self._recorder.recording_finished.connect(self._on_recording_finished)
        self._recorder.capture_backend_changed.connect(self._on_capture_backend_changed)

        self._hotkeys.record_toggle_pressed.connect(self._on_record_toggle)

        self._connect_exporter_signals_if_ready()

        # countdown overlay (covers the central widget)
        self._countdown = CountdownOverlay(central)
        self._countdown.setVisible(False)
        self._countdown.finished.connect(self._do_start_recording)

        # processing overlay (shown while finishing a recording)
        self._processing_overlay = ProcessingOverlay(central)
        self._processing_overlay.setVisible(False)

        # ── deferred tray icon (created after window shows) ─────────
        self._tray_icon = None

        # Apply persisted background / frame presets to UI
        if self._bg_preset:
            self._preview.set_bg_preset(self._bg_preset)
            self._editor.set_background_by_name(self._bg_preset.name)
        if self._frame_preset:
            self._preview.set_frame_preset(self._frame_preset)
            self._editor.set_frame_by_name(self._frame_preset.name)
        if self._click_preset:
            self._preview.set_click_preset(self._click_preset)
            self._editor.set_click_preset(self._click_preset)

        # Restore persisted encoder preference
        saved_encoder = self._settings.value("encoderId", "")
        if saved_encoder:
            self._editor.set_encoder_by_id(saved_encoder)

        # Show initial title (Untitled project)
        self._update_title()

        # Register persistent Ctrl+Shift+R hotkey
        self._hotkeys.register_record_hotkey()

        # Deferred init — runs right after the event loop starts
        # (tray icon, encoder label, etc.)
        QTimer.singleShot(0, self._deferred_init)

    # ════════════════════════════════════════════════════════════════
    #  Deferred initialization (runs after window.show())
    # ════════════════════════════════════════════════════════════════

    def _deferred_init(self) -> None:
        """Complete heavy initialization after the window is visible.

        Called via ``QTimer.singleShot(0, ...)`` so the window paints
        immediately.  Creates the system tray icon, updates the encoder
        label, and pre-loads TTS voices if configured.
        """
        self._ensure_tray_icon()
        self._update_encoder_label(self._editor.encoder_id)
        # Auto-load TTS voices in background if AI settings are already configured
        ai = self._load_ai_settings()
        if ai.tts_configured:
            self._status_text.setText("Loading TTS voices\u2026")
            self._editor._load_tts_voices(ai.endpoint, ai.api_key)
            # Clear status after a delay (voices load on background thread)
            QTimer.singleShot(5000, lambda: (
                self._status_text.setText("Ready")
                if self._status_text.text() == "Loading TTS voices\u2026"
                else None
            ))

    def _ensure_tray_icon(self) -> None:
        """Create the system tray icon on first use."""
        if self._tray_icon is not None:
            return
        self._tray_icon = QSystemTrayIcon(create_app_icon(), self)
        tray_menu = QMenu()
        tray_menu.addAction("Show FollowCursor", self._restore_from_tray)
        tray_menu.addAction("Stop Recording", self._stop_recording)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)

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
        self._btn_record_view = self._make_sidebar_btn(
            load_icon("record", variant="filled", color=T.BRAND), "Record", active=True
        )
        self._btn_record_view.clicked.connect(lambda: self._set_view("record"))

        self._btn_edit_view = self._make_sidebar_btn(
            load_icon("play", color=T.FG_PRIMARY), "Edit"
        )
        self._btn_edit_view.clicked.connect(lambda: self._set_view("edit"))

        sep = QFrame()
        sep.setFixedSize(40, 1)
        sep.setStyleSheet("background-color: #2d2b45;")

        self._btn_load = self._make_sidebar_btn(
            load_icon("folder_open", color=T.FG_PRIMARY), "Open"
        )
        self._btn_load.clicked.connect(self._load_session)

        self._btn_save = self._make_sidebar_btn(
            load_icon("save", color=T.FG_PRIMARY), "Save"
        )
        self._btn_save.clicked.connect(self._save_session)

        for w in [self._btn_record_view, self._btn_edit_view, sep, self._btn_load, self._btn_save]:
            layout.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)

        # Fluent 2 — focus ring glow on sidebar navigation buttons
        for btn in (self._btn_record_view, self._btn_edit_view,
                    self._btn_load, self._btn_save):
            install_focus_ring(btn)

        layout.addStretch()
        return sidebar

    @staticmethod
    def _make_sidebar_btn(icon: QIcon, label: str, active: bool = False) -> QToolButton:
        btn = QToolButton()
        btn.setIcon(icon)
        btn.setIconSize(QSize(20, 20))
        btn.setText(label)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
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

        self._btn_change_source = QPushButton("  Change Screen")
        self._btn_change_source.setIcon(load_icon("desktop", color=T.FG_PRIMARY))
        self._btn_change_source.setObjectName("CtrlBtn")
        self._btn_change_source.clicked.connect(self._select_source)
        self._btn_change_source.setVisible(False)

        self._btn_record = QPushButton("  Record  (Ctrl+Shift+R)")
        self._btn_record.setIcon(load_icon("record", variant="filled", color=T.DANGER))
        self._btn_record.setObjectName("RecordBtn")
        self._btn_record.clicked.connect(self._start_recording)
        self._btn_record.setVisible(False)

        self._btn_stop = QPushButton("  Stop Recording")
        self._btn_stop.setIcon(load_icon("stop", variant="filled", color=T.DANGER))
        self._btn_stop.setObjectName("StopBtn")
        self._btn_stop.clicked.connect(self._stop_recording)
        self._btn_stop.setVisible(False)

        layout.addWidget(self._btn_change_source)
        layout.addWidget(self._btn_record)
        layout.addWidget(self._btn_stop)

        # Fluent 2 — keyboard focus glow on control buttons
        for btn in (self._btn_change_source, self._btn_record, self._btn_stop):
            install_focus_ring(btn)

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
        self._btn_clipchamp = QPushButton("  Show in folder")
        self._btn_clipchamp.setIcon(load_icon("folder_open", color=T.FG_PRIMARY))
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

        # Fluent 2 — focus ring on status-bar button
        install_focus_ring(self._btn_clipchamp)

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

        # Prompt if there are unsaved edits from the previous session
        if self._unsaved_changes and self._video_path:
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Unsaved Changes")
            dlg.setText("Starting a new recording will discard unsaved changes.\nDo you want to save first?")
            dlg.setIcon(QMessageBox.Icon.Warning)
            btn_save = dlg.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
            dlg.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = dlg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            dlg.setDefaultButton(btn_cancel)
            dlg.exec()
            clicked = dlg.clickedButton()
            if clicked == btn_cancel:
                return
            if clicked == btn_save:
                self._save_session()
                if self._unsaved_changes:
                    return  # user cancelled save dialog

        # Show countdown overlay, then start recording
        self._btn_record.setVisible(False)
        self._btn_change_source.setVisible(False)
        self._countdown.setGeometry(self.centralWidget().rect())
        self._countdown.start()

    def _reset_session(self) -> None:
        """Clear all state from the previous recording/editing session.

        Called before starting a new recording so that no stale data
        (voiceovers, trim, undo history, playback position, etc.)
        leaks into the new session.
        """
        # Stop any active playback and release video handle
        self._preview.stop_playback()
        self._stop_voiceover_audio()
        self._zoom_sync_timer.stop()

        # Zoom / keyframe state
        self._zoom_engine.clear()
        self._zoom_engine.clear_history()

        # Session data
        self._mouse_track = []
        self._mouse_track_timestamps = []
        self._actual_fps_override = 0.0

        # Voiceover / trim / project / video segments
        self._voiceover_segments = []
        self._video_segments = []
        self._chapters = []
        # Keep zoom engine segments in sync with session segments
        self._zoom_engine.video_segments = []
        self._vo_played_ids = set()
        self._trim_start_ms = 0.0
        self._trim_end_ms = 0.0
        self._preview.set_playback_end(0.0)
        self._project_path = ""
        self._unsaved_changes = False
        self._output_dim = "auto"
        self._update_title()

    def _do_start_recording(self) -> None:
        """Called when the 3-2-1 countdown finishes."""
        import time as _time

        try:
            self._reset_session()
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

        # Stop mouse tracker here (main thread) — its QTimer must not be
        # stopped from _FinalizeWorker's background thread.
        self._mouse_positions = self._mouse_tracker.stop()

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
            mouse_positions=self._mouse_positions,
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
            self._mouse_track_timestamps = [mp.timestamp for mp in self._mouse_track]
            self._key_events = key_events
            self._click_events = click_events
            self._zoom_engine.click_events = self._click_events
            self._zoom_engine.video_segments = self._video_segments
            self._zoom_engine.voiceover_segments = self._voiceover_segments
            self._frame_timestamps = frame_timestamps
            self._actual_fps_override = actual_fps

            # Initialize a single video segment spanning the full recording
            self._video_segments = [VideoSegment.create(start_ms=0.0, end_ms=self._rec_duration_ms)]
            self._zoom_engine.video_segments = self._video_segments

            self._processing_overlay.hide_overlay()
            self._status_text.setText("Ready")
            self._unsaved_changes = True
            self._update_title()
            # Push keystroke data to preview for live rendering
            self._preview.set_keystroke_data(self._key_events, self._keystroke_config)
            self._set_view("edit")
        except Exception:
            logger.exception("Error in post-recording finalization")
            self._processing_overlay.hide_overlay()
            self._status_text.setText("Error finalizing recording")

        # Clean up worker reference
        self._finalize_worker.deleteLater()
        self._finalize_worker = None

    def _remux_with_correct_fps(self) -> None:
        """Remux the recording so its metadata FPS matches reality.

        The recording pipe tells ffmpeg ``-r {target_fps}`` (e.g. 60) but
        WGC only delivers changed frames, so the real write-rate is much
        lower (e.g. 7 fps).  This makes the container claim 60 fps for
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
                "Video metadata already correct (meta_fps=%.1f, real_fps=%.2f)",
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

        temp_output = self._video_path + ".remux.mp4"
        cmd = [
            ffmpeg, "-y",
            "-r", f"{correct_fps:.4f}",
            "-i", self._video_path,
            "-c:v", "copy",
            temp_output,
        ]
        # Scale timeout with recording length; -c:v copy is fast but large
        # files on slow storage can exceed the old 60 s default.
        remux_timeout = max(120, int(self._rec_duration_ms / 1000) + 30)
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=remux_timeout,
                **subprocess_kwargs(),
            )
            if result.returncode == 0 and os.path.isfile(temp_output):
                os.replace(temp_output, self._video_path)
                self._actual_fps_override = correct_fps
                logger.info(
                    "Remuxed video: %d frames, fps %.1f → %.2f",
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
            # Stop playback and zoom sync from the edit session
            self._preview.stop_playback()
            self._zoom_sync_timer.stop()
            self._stop_voiceover_audio()

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
            self._title_bar.set_discard_visible(bool(self._video_path))
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
        self._ensure_tray_icon()
        if self._tray_icon:
            self._tray_icon.show()
            self._tray_icon.setToolTip("FollowCursor — Recording… (Ctrl+Shift+R to stop)")
        self.hide()

    def _restore_from_tray(self) -> None:
        """Show the window again and hide the tray icon."""
        if self._tray_icon:
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
        out_dur = self._zoom_engine.compute_output_duration(
            self._rec_duration_ms, self._trim_start_ms, self._trim_end_ms,
        )
        self._editor.refresh(
            self._zoom_engine.keyframes,
            self._mouse_track,
            self._rec_duration_ms,
            self._monitor_rect,
            self._key_events,
            self._click_events,
            self._trim_start_ms,
            self._trim_end_ms,
            output_duration=out_dur,
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
            self._voiceover_segments,
            self._video_segments,
        )
        # Keep debug overlay in sync with keyframes
        self._preview.set_debug_keyframes(self._zoom_engine.keyframes)

    def _on_auto_keyframes(self, keyframes) -> None:
        """Handle auto-generated keyframes from activity analysis."""
        # Confirm if there are existing zoom keyframes that will be replaced
        existing = [kf for kf in self._zoom_engine.keyframes if kf.zoom > 1.01]
        if existing:
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Replace existing zooms?")
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setText(
                f"You have <b>{len(existing)}</b> existing zoom section"
                f"{'s' if len(existing) != 1 else ''}.<br><br>"
                "Auto-generating will <b>replace all</b> of them with "
                f"<b>{sum(1 for kf in keyframes if kf.zoom > 1.0)}</b> "
                "new section(s)."
            )
            dlg.addButton("Replace", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = dlg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            dlg.setDefaultButton(btn_cancel)
            dlg.setStyleSheet(
                "QMessageBox { background: #1b1a2e; }"
                "QMessageBox QLabel { color: #e4e4ed; font-size: 13px; }"
                "QPushButton { min-width: 80px; min-height: 28px;"
                "  background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58;"
                "  border-radius: 6px; padding: 4px 16px; }"
                "QPushButton:hover { background: #8b5cf6; }"
            )
            dlg.exec()
            if dlg.clickedButton() == btn_cancel:
                return

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

    def _on_click_changed(self, preset) -> None:
        """Handle click effect preset change from editor panel."""
        self._click_preset = preset
        self._preview.set_click_preset(preset)
        # Persist to QSettings
        self._settings.setValue("clickPreset", preset.name)

    def _on_keystroke_config_changed(self, config) -> None:
        """Handle keystroke overlay configuration changes."""
        self._keystroke_config = config
        # Persist to QSettings
        self._settings.setValue("keystroke/enabled", config.enabled)
        self._settings.setValue("keystroke/position", config.position)
        self._settings.setValue("keystroke/style", config.style)
        self._settings.setValue("keystroke/filterMode", config.filter_mode)
        # Update preview with keystroke data
        self._preview.set_keystroke_data(self._key_events, self._keystroke_config)
        self._mark_dirty()

    def _on_annotation_added(self, annot_type: str, annotation) -> None:
        """Handle new annotation added from editor panel."""
        from .models import AnnotationCollection
        
        if self._annotations is None:
            self._annotations = AnnotationCollection()
        
        # Add to the appropriate list
        if annot_type == "text":
            if self._annotations.texts is None:
                self._annotations.texts = []
            self._annotations.texts.append(annotation)
        elif annot_type == "arrow":
            if self._annotations.arrows is None:
                self._annotations.arrows = []
            self._annotations.arrows.append(annotation)
        elif annot_type == "highlight":
            if self._annotations.highlights is None:
                self._annotations.highlights = []
            self._annotations.highlights.append(annotation)
        
        # Update preview
        self._preview.set_annotations(self._annotations)
        self._mark_dirty()
        logger.info("Annotation added: %s", annot_type)

    def _on_annotation_removed(self, annot_type: str, annot_id: str) -> None:
        """Handle annotation removed from editor panel."""
        if not self._annotations:
            return
        
        # Remove from the appropriate list
        if annot_type == "text" and self._annotations.texts:
            self._annotations.texts = [
                a for a in self._annotations.texts if a.id != annot_id
            ]
        elif annot_type == "arrow" and self._annotations.arrows:
            self._annotations.arrows = [
                a for a in self._annotations.arrows if a.id != annot_id
            ]
        elif annot_type == "highlight" and self._annotations.highlights:
            self._annotations.highlights = [
                a for a in self._annotations.highlights if a.id != annot_id
            ]
        
        # Update preview
        self._preview.set_annotations(self._annotations)
        self._mark_dirty()
        logger.info("Annotation removed: %s %s", annot_type, annot_id)

    def _on_annotation_updated(self, annot_type: str, annotation) -> None:
        """Handle annotation updated from editor panel."""
        if self._annotations is None:
            return

        # Update the matching annotation by id
        if annot_type == "text" and self._annotations.texts:
            self._annotations.texts = [
                annotation if a.id == annotation.id else a
                for a in self._annotations.texts
            ]
        elif annot_type == "arrow" and self._annotations.arrows:
            self._annotations.arrows = [
                annotation if a.id == annotation.id else a
                for a in self._annotations.arrows
            ]
        elif annot_type == "highlight" and self._annotations.highlights:
            self._annotations.highlights = [
                annotation if a.id == annotation.id else a
                for a in self._annotations.highlights
            ]

        self._preview.set_annotations(self._annotations)
        self._mark_dirty()
        logger.info("Annotation updated: %s", annot_type)

    def _on_auto_detect_chapters(self) -> None:
        """Handle auto-detect chapters request from editor panel."""
        from .activity_analyzer import detect_chapters
        chapters = detect_chapters(
            self._mouse_track,
            self._key_events,
            self._click_events,
            self._rec_duration_ms
        )
        self._chapters = chapters
        self._timeline.chapters = chapters
        self._timeline.update()
        self._mark_dirty()
        self._editor.set_chapters_status(f"{len(chapters)} chapter(s) detected")
        logger.info("Auto-detected %d chapters", len(chapters))

    def _on_chapter_added(self, chapter) -> None:
        """Handle manual chapter addition from editor panel."""
        # Auto-number if name is just "Chapter"
        if chapter.name == "Chapter":
            existing_nums = []
            for c in self._chapters:
                if c.name.startswith("Chapter "):
                    try:
                        num = int(c.name.split()[-1])
                        existing_nums.append(num)
                    except ValueError:
                        pass
            next_num = max(existing_nums, default=0) + 1
            chapter.name = f"Chapter {next_num}"
        
        self._chapters.append(chapter)
        self._chapters.sort(key=lambda c: c.timestamp_ms)
        self._timeline.chapters = self._chapters
        self._timeline.update()
        self._mark_dirty()
        logger.info("Chapter added: %s at %.2fs", chapter.name, chapter.timestamp_ms / 1000)

    def _on_chapter_removed(self, timestamp_ms: int) -> None:
        """Handle chapter removal."""
        self._chapters = [c for c in self._chapters if c.timestamp_ms != timestamp_ms]
        self._timeline.chapters = self._chapters
        self._timeline.update()
        self._mark_dirty()
        logger.info("Chapter removed at %.2fs", timestamp_ms / 1000)

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

    # ── AI features ──────────────────────────────────────────────────────

    def _load_ai_settings(self):
        """Load AI settings from QSettings."""
        from .ai_service import AISettings
        from .credentials import unprotect
        return AISettings(
            endpoint=self._settings.value("ai/endpoint", ""),
            api_key=unprotect(self._settings.value("ai/apiKey", "")),
            chat_model=self._settings.value("ai/chatModel", ""),
            tts_voice=self._settings.value("ai/ttsVoice", "en-US-Ava:DragonHDLatestNeural"),
        )

    def _ensure_ai_worker(self):
        """Create the AI worker thread if needed."""
        if self._ai_worker is None:
            from .ai_service import AIWorker
            self._ai_worker = AIWorker(parent=self)
            self._ai_worker.zoom_result.connect(self._on_ai_zoom_result)
            self._ai_worker.tts_result.connect(self._on_ai_tts_result)
            self._ai_worker.error.connect(self._on_ai_error)
            self._ai_worker.status.connect(self._on_ai_status)
        return self._ai_worker

    def _on_ai_zoom_requested(self, max_clusters: int, zoom_level: float, min_gap_ms: int) -> None:
        """Handle AI zoom analysis request from editor panel."""
        ai_settings = self._load_ai_settings()
        if not ai_settings.chat_configured:
            self._editor.set_ai_zoom_status(
                "AI not configured. Open \u2699 Settings \u2192 AI Settings."
            )
            return
        worker = self._ensure_ai_worker()
        if worker.isRunning():
            self._editor.set_ai_zoom_status("AI operation already in progress\u2026")
            return
        worker.run_zoom_analysis(
            ai_settings,
            mouse_track=self._mouse_track,
            monitor_rect=self._monitor_rect,
            duration_ms=self._rec_duration_ms,
            key_events=self._key_events or None,
            click_events=self._click_events or None,
            max_clusters=max_clusters,
            zoom_level=zoom_level,
            min_gap_ms=min_gap_ms,
        )
        self._editor.set_ai_busy(True)

    def _on_ai_zoom_result(self, keyframes) -> None:
        """Handle AI zoom analysis results — same flow as local auto-keyframes."""
        self._status_text.setText("Ready")
        self._editor.set_ai_busy(False)
        if not keyframes:
            self._editor.set_ai_zoom_status("AI found no significant activity.")
            return
        n_clusters = sum(1 for kf in keyframes if kf.zoom > 1.0)
        self._editor.set_ai_zoom_status(
            f"AI generated {len(keyframes)} keyframes from {n_clusters} cluster"
            f"{'s' if n_clusters != 1 else ''}."
        )
        # Reuse the same flow as local auto-keyframes
        self._on_auto_keyframes(keyframes)

    # ── Voiceover segments ──────────────────────────────────────────

    def _on_add_voiceover_requested(self, timestamp_ms: float, voice: str) -> None:
        """Show dialog to add a voiceover segment at the given time."""
        if timestamp_ms < 0:
            timestamp_ms = self._playback_time
        from .models import VoiceoverSegment
        dlg = _VoiceoverDialog(timestamp_ms, voice, parent=self)
        result = dlg.exec()
        if result == _VoiceoverDialog.RESULT_OK:
            # Remember the chosen voice for next time
            self._settings.setValue("ai/ttsVoice", dlg.voice)
            # Synthesize + add the segment
            seg = VoiceoverSegment.create(
                timestamp=dlg.timestamp_ms,
                text=dlg.text,
                voice=dlg.voice,
                rate=dlg.rate,
                volume=dlg.volume,
            )
            self._voiceover_segments.append(seg)
            self._voiceover_segments.sort(key=lambda s: s.timestamp)
            self._mark_dirty()
            self._refresh_editor()
            # Reuse cached preview audio if available
            cached = dlg.cached_audio_path
            if cached:
                import shutil
                import tempfile
                dest = os.path.join(
                    tempfile.gettempdir(), f"followcursor_vo_{seg.id[:8]}.wav"
                )
                shutil.copy2(cached, dest)
                seg.audio_path = dest
                seg.duration_ms = self._probe_audio_duration(dest)
                self._mark_dirty()
                self._refresh_editor()
                self._editor.set_voiceover_status(
                    f"\u2713 Voiceover added ({seg.duration_ms / 1000:.1f}s)."
                )
            else:
                self._synthesize_voiceover(seg)

    def _on_voiceover_clicked(self, seg_id: str) -> None:
        """Show edit/delete dialog for a voiceover segment."""
        seg = next((s for s in self._voiceover_segments if s.id == seg_id), None)
        if seg is None:
            return
        dlg = _VoiceoverDialog(
            seg.timestamp, seg.voice, text=seg.text,
            title="Edit Voiceover",
            is_edit=True,
            rate=seg.rate,
            volume=seg.volume,
            parent=self,
        )
        result = dlg.exec()
        if result == _VoiceoverDialog.RESULT_OK:
            # Remember the chosen voice for next time
            self._settings.setValue("ai/ttsVoice", dlg.voice)
            seg.timestamp = dlg.timestamp_ms
            seg.text = dlg.text
            seg.voice = dlg.voice
            seg.rate = dlg.rate
            seg.volume = dlg.volume
            self._voiceover_segments.sort(key=lambda s: s.timestamp)
            self._mark_dirty()
            self._refresh_editor()
            # Reuse cached preview audio if available
            cached = dlg.cached_audio_path
            if cached:
                import shutil
                import tempfile
                dest = os.path.join(
                    tempfile.gettempdir(), f"followcursor_vo_{seg.id[:8]}.wav"
                )
                shutil.copy2(cached, dest)
                seg.audio_path = dest
                seg.duration_ms = self._probe_audio_duration(dest)
                self._mark_dirty()
                self._refresh_editor()
                self._editor.set_voiceover_status(
                    f"\u2713 Voiceover updated ({seg.duration_ms / 1000:.1f}s)."
                )
            else:
                self._synthesize_voiceover(seg)
        elif result == _VoiceoverDialog.RESULT_DELETE:
            self._voiceover_segments = [s for s in self._voiceover_segments if s.id != seg_id]
            self._mark_dirty()
            self._refresh_editor()
            self._editor.set_voiceover_status("Voiceover removed.")

    def _on_voiceover_deleted(self, seg_id: str) -> None:
        """Handle direct voiceover deletion (keyboard Delete key)."""
        self._voiceover_segments = [s for s in self._voiceover_segments if s.id != seg_id]
        self._mark_dirty()
        self._refresh_editor()
        self._editor.set_voiceover_status("Voiceover removed.")

    def _on_voiceover_moved(self, seg_id: str, new_time: float) -> None:
        """Handle voiceover segment drag on the timeline."""
        seg = next((s for s in self._voiceover_segments if s.id == seg_id), None)
        if seg is None:
            return
        seg.timestamp = max(0.0, new_time)
        self._voiceover_segments.sort(key=lambda s: s.timestamp)
        self._mark_dirty()
        self._refresh_editor()

    def _synthesize_voiceover(self, seg) -> None:
        """Synthesize TTS audio for a voiceover segment."""
        ai_settings = self._load_ai_settings()
        if not ai_settings.tts_configured:
            self._editor.set_voiceover_status(
                "TTS not configured. Set a TTS model in \u2699 AI Settings."
            )
            return
        worker = self._ensure_ai_worker()
        if worker.isRunning():
            self._editor.set_voiceover_status("AI operation already in progress\u2026")
            return
        ai_settings.tts_voice = seg.voice
        import tempfile
        output_path = os.path.join(
            tempfile.gettempdir(), f"followcursor_vo_{seg.id[:8]}.wav"
        )
        worker.run_tts(ai_settings, seg.id, seg.text, output_path,
                       rate=seg.rate, volume=seg.volume)
        self._editor.set_voiceover_status("Synthesizing speech\u2026")
        self._editor.set_ai_busy(True)

    def _on_ai_tts_result(self, seg_id: str, audio_path: str) -> None:
        """Handle TTS audio file result — associate with the voiceover segment."""
        self._status_text.setText("Ready")
        self._editor.set_ai_busy(False)
        seg = next((s for s in self._voiceover_segments if s.id == seg_id), None)
        if seg is None:
            return
        seg.audio_path = audio_path
        # Probe duration with ffmpeg
        seg.duration_ms = self._probe_audio_duration(audio_path)
        self._mark_dirty()
        self._refresh_editor()
        self._editor.set_voiceover_status(
            f"\u2713 Speech synthesized ({seg.duration_ms / 1000:.1f}s). "
            "Will be included in export."
        )

    def _probe_audio_duration(self, path: str) -> float:
        """Get the duration of an audio file in milliseconds via ffprobe/ffmpeg."""
        try:
            from .utils import ffmpeg_exe, subprocess_kwargs
            import subprocess
            ffmpeg = ffmpeg_exe()
            result = subprocess.run(
                [ffmpeg, "-i", path, "-f", "null", "-"],
                capture_output=True, timeout=10,
                **subprocess_kwargs(),
            )
            import re
            stderr = result.stderr.decode(errors="replace")
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", stderr)
            if m:
                h, mi, s, cs = int(m[1]), int(m[2]), int(m[3]), int(m[4])
                return (h * 3600 + mi * 60 + s) * 1000 + cs * 10
        except Exception:
            pass
        return 3000.0  # fallback estimate

    @staticmethod
    def _fmt_time(ms: float) -> str:
        s = int(ms / 1000)
        return f"{s // 60}:{s % 60:02d}"

    def _on_ai_error(self, task: str, msg: str) -> None:
        """Handle AI operation errors."""
        logger.error("AI error (%s): %s", task, msg)
        self._status_text.setText("Ready")
        self._editor.set_ai_busy(False)
        truncated = msg[:200]
        if task == "zoom":
            self._editor.set_ai_zoom_status(f"AI error: {truncated}")
        else:
            self._editor.set_voiceover_status(f"AI error: {truncated}")

    def _on_ai_status(self, msg: str) -> None:
        """Handle AI status updates."""
        self._status_text.setText(msg)

    # ── undo / redo ─────────────────────────────────────────────────

    def _undo(self) -> None:
        """Undo the last zoom/click/segment change."""
        if self._zoom_engine.undo():
            self._click_events = self._zoom_engine.click_events
            self._video_segments = self._zoom_engine.video_segments
            self._voiceover_segments = self._zoom_engine.voiceover_segments
            self._zoom_engine.update(self._playback_time)
            self._preview.set_zoom(
                self._zoom_engine.current_zoom,
                self._zoom_engine.current_pan_x,
                self._zoom_engine.current_pan_y,
            )
            self._preview.set_cursor_data(
                self._mouse_track, self._monitor_rect, self._click_events
            )
            self._refresh_editor()

    def _redo(self) -> None:
        """Redo the last undone zoom/click/segment change."""
        if self._zoom_engine.redo():
            self._click_events = self._zoom_engine.click_events
            self._video_segments = self._zoom_engine.video_segments
            self._voiceover_segments = self._zoom_engine.voiceover_segments
            self._zoom_engine.update(self._playback_time)
            self._preview.set_zoom(
                self._zoom_engine.current_zoom,
                self._zoom_engine.current_pan_x,
                self._zoom_engine.current_pan_y,
            )
            self._preview.set_cursor_data(
                self._mouse_track, self._monitor_rect, self._click_events
            )
            self._refresh_editor()

    # ── trim ────────────────────────────────────────────────────────

    def _on_trim_changed(self, start_ms: float, end_ms: float) -> None:
        """Handle trim handle changes from the timeline."""
        # Debounced undo push — one snapshot per drag operation
        if not self._drag_undo_pushed:
            self._zoom_engine.push_undo()
            self._drag_undo_pushed = True
        self._trim_start_ms = start_ms
        self._trim_end_ms = end_ms
        self._zoom_engine.trim_start_ms = start_ms
        self._zoom_engine.trim_end_ms = end_ms
        self._mark_dirty()

    def _on_trim_reset(self) -> None:
        """Handle trim reset from the timeline (right-click → Reset trim)."""
        self._zoom_engine.push_undo()
        self._trim_start_ms = 0.0
        self._trim_end_ms = 0.0
        self._zoom_engine.trim_start_ms = 0.0
        self._zoom_engine.trim_end_ms = 0.0
        self._mark_dirty()
        self._refresh_editor()

    # ── segment splitting ───────────────────────────────────────────

    def _split_at_time(self, time_ms: float) -> None:
        """Split the recording at *time_ms*, creating two adjacent segments.

        The split is rejected when *time_ms* is within 500 ms of an
        existing segment boundary or a trim handle.
        """
        MIN_GAP_MS = 500.0
        segments = self._zoom_engine.video_segments

        # Effective trim bounds
        eff_start = self._trim_start_ms if self._trim_start_ms > 0 else 0.0
        eff_end = self._trim_end_ms if self._trim_end_ms > 0 else self._rec_duration_ms

        # Reject if too close to a trim handle
        if abs(time_ms - eff_start) < MIN_GAP_MS or abs(time_ms - eff_end) < MIN_GAP_MS:
            return

        # Reject if too close to any existing segment boundary
        for seg in segments:
            if abs(time_ms - seg.start_ms) < MIN_GAP_MS:
                return
            if abs(time_ms - seg.end_ms) < MIN_GAP_MS:
                return

        # Find the segment that contains time_ms
        target = None
        for seg in segments:
            if seg.start_ms < time_ms < seg.end_ms:
                target = seg
                break
        if target is None:
            return

        # Push undo before mutation
        self._zoom_engine.push_undo()

        # Create two new segments replacing the target
        seg_left = VideoSegment.create(start_ms=target.start_ms, end_ms=time_ms, speed=target.speed)
        seg_right = VideoSegment.create(start_ms=time_ms, end_ms=target.end_ms, speed=target.speed)

        idx = segments.index(target)
        segments[idx:idx + 1] = [seg_left, seg_right]

        self._video_segments = segments
        self._mark_dirty()
        self._refresh_editor()

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
            label = "GDI"
        else:
            label = backend
        self._capture_mode_label.setText(label)
        self._capture_mode_label.setVisible(True)
        logger.info("Capture backend: %s", backend)

    # ── zoom helpers ────────────────────────────────────────────────

    def _lookup_mouse_pan(self, time_ms: float) -> tuple:
        """Find the recorded mouse position at a given playback time and return
        normalized pan coordinates (0-1).  Falls back to (0.5, 0.5)."""
        if not self._mouse_track or not self._monitor_rect:
            return 0.5, 0.5
        import bisect
        # Use pre-built timestamp cache for O(log n) lookup without per-call allocation
        timestamps = self._mouse_track_timestamps
        idx = bisect.bisect_left(timestamps, time_ms)
        # Pick the closer of the two surrounding samples
        if idx == 0:
            best = self._mouse_track[0]
        elif idx >= len(self._mouse_track):
            best = self._mouse_track[-1]
        else:
            before = self._mouse_track[idx - 1]
            after = self._mouse_track[idx]
            if (time_ms - before.timestamp) <= (after.timestamp - time_ms):
                best = before
            else:
                best = after
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
            zoom_out_time = min(timestamp + 1500, self._rec_duration_ms)
            zoom_out_dur = 600.0  # transition back to 1×

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

            # Only add if there's no existing zoom-out between this
            # zoom-in and the next zoom-in (scoped check)
            search_end = next_zoom_in.timestamp if next_zoom_in else float("inf")
            has_zoom_out = any(
                k.timestamp > timestamp and k.timestamp <= search_end
                and k.zoom <= 1.01
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
            if not self._drag_undo_pushed:
                self._zoom_engine.push_undo()
                self._drag_undo_pushed = True
            self._mark_dirty()

        # Clamp so it doesn’t cross its neighbours
        MIN_KF_GAP_MS = 100  # keep keyframes at least 100ms apart
        prev_kf = kfs[moved_idx - 1] if moved_idx > 0 else None
        next_kf = kfs[moved_idx + 1] if moved_idx + 1 < len(kfs) else None

        if prev_kf is not None:
            earliest = prev_kf.timestamp + MIN_KF_GAP_MS
            new_time_ms = max(new_time_ms, earliest)
        if next_kf is not None:
            latest = next_kf.timestamp - MIN_KF_GAP_MS
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

    def _on_segment_clicked(self, start_kf_id: str, click_time_ms: float = 0.0) -> None:
        """Handle clicking on a zoom segment body — show depth picker + pan point + delete."""
        from .widgets.editor_panel import ZOOM_DEPTHS

        # Find the keyframe
        target_kf = None
        end_kf = None
        sorted_kfs = sorted(self._zoom_engine.keyframes, key=lambda k: k.timestamp)
        for i, kf in enumerate(sorted_kfs):
            if kf.id == start_kf_id:
                target_kf = kf
                # Find segment end (first kf with zoom <= 1.01 after start)
                for j in range(i + 1, len(sorted_kfs)):
                    if sorted_kfs[j].zoom <= 1.01:
                        end_kf = sorted_kfs[j]
                        break
                break
        if target_kf is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58;"
            "        border-radius: 6px; padding: 4px 0; }"
            "QMenu::item { padding: 6px 16px; }"
            "QMenu::item:selected { background: #8b5cf6; border-radius: 4px; margin: 0 4px; }"
            "QMenu::item:disabled { color: #6c6890; }"
            "QMenu::separator { height: 1px; background: #3d3a58; margin: 4px 8px; }"
        )

        # Section header
        header = menu.addAction("  Zoom  ({:.2f}×)".format(target_kf.zoom))
        header.setIcon(load_icon("search", color=T.FG_PRIMARY))
        header.setEnabled(False)
        menu.addSeparator()

        for label, level in ZOOM_DEPTHS.items():
            check = "  ✓" if abs(target_kf.zoom - level) < 0.01 else ""
            act = menu.addAction(f"    {label}  ({level}×){check}")
            act.triggered.connect(
                lambda checked, z=level: self._set_segment_zoom(start_kf_id, z)
            )

        menu.addSeparator()

        # ── Speed submenu ───────────────────────────────────────────
        speed_menu = menu.addMenu("  Speed")
        speed_menu.setIcon(load_icon("gauge", color=T.FG_PRIMARY))
        speed_menu.setStyleSheet(menu.styleSheet())
        current_speed = target_kf.speed
        # 0.5, 0.75, 1.0, 1.25, 1.5, ... 10.0 in 0.25 steps
        speed_val = 0.5
        while speed_val <= 10.0 + 0.001:
            check = "  ✓" if abs(current_speed - speed_val) < 0.01 else ""
            disp = round(speed_val, 2)
            speed_text = str(int(disp)) if disp == int(disp) else f"{disp:.2f}".rstrip("0").rstrip(".")
            label = f"{speed_text}×{check}"
            act = speed_menu.addAction(label)
            act.triggered.connect(
                lambda checked, s=speed_val: self._set_segment_speed(start_kf_id, s)
            )
            speed_val += 0.25

        menu.addSeparator()

        # Centroid repositioning
        centroid_act = menu.addAction("  Pick zoom center on preview\u2026")
        centroid_act.setIcon(load_icon("location", color=T.FG_PRIMARY))
        centroid_act.triggered.connect(
            lambda: self._enter_centroid_pick(start_kf_id)
        )

        menu.addSeparator()
        del_act = menu.addAction("  Delete zoom section")
        del_act.setIcon(load_icon("delete", color=T.DANGER))
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

    def _set_segment_speed(self, kf_id: str, new_speed: float) -> None:
        """Update the playback speed of a segment's start keyframe."""
        self._zoom_engine.push_undo()
        self._mark_dirty()
        for kf in self._zoom_engine.keyframes:
            if kf.id == kf_id:
                kf.speed = new_speed
                break
        self._refresh_editor()

    def _add_pan_point(self, segment_start_id: str, time_ms: float) -> None:
        """Add a pan waypoint inside a zoom segment at *time_ms*.

        The new keyframe inherits the segment's zoom level but gets its
        (x, y) from the mouse track at that timestamp.  This creates a
        smooth pan-while-zoomed path through intermediate points.
        """
        pan_x, pan_y = self._lookup_mouse_pan(time_ms)
        self._add_pan_point_at(segment_start_id, time_ms, pan_x, pan_y)

    def _add_pan_point_at(self, segment_start_id: str, time_ms: float,
                          pan_x: float, pan_y: float) -> None:
        """Add a pan waypoint with explicit (pan_x, pan_y) coordinates."""
        # Find the segment's start keyframe to inherit its zoom level
        start_kf = None
        for kf in self._zoom_engine.keyframes:
            if kf.id == segment_start_id:
                start_kf = kf
                break
        if start_kf is None:
            return

        # Compute the current pan position at this time to scale duration
        # by distance — longer pans take proportionally longer.
        _, cur_x, cur_y = self._zoom_engine.compute_at(time_ms)
        import math
        dist = math.hypot(pan_x - cur_x, pan_y - cur_y)
        # Scale: 400ms base for tiny moves, up to 800ms for full-screen pans
        pan_duration = max(400.0, min(800.0, 400.0 + dist * 800.0))

        self._zoom_engine.push_undo()
        pan_kf = ZoomKeyframe.create(
            timestamp=time_ms,
            zoom=start_kf.zoom,
            x=pan_x,
            y=pan_y,
            duration=pan_duration,
            reason="Pan point",
        )
        self._zoom_engine.add_keyframe(pan_kf)
        self._mark_dirty()

        self._zoom_engine.update(self._playback_time)
        self._preview.set_zoom(
            self._zoom_engine.current_zoom,
            self._zoom_engine.current_pan_x,
            self._zoom_engine.current_pan_y,
        )
        self._refresh_editor()

    def _on_pan_point_clicked(self, pan_kf_id: str, segment_start_id: str) -> None:
        """Right-click on a pan point marker — show context menu."""
        # Find the pan point keyframe
        target_kf = None
        for kf in self._zoom_engine.keyframes:
            if kf.id == pan_kf_id:
                target_kf = kf
                break
        if target_kf is None:
            return

        # Count pan points in this segment to show the number
        sorted_kfs = sorted(self._zoom_engine.keyframes, key=lambda k: k.timestamp)
        start_kf = None
        end_kf = None
        for i, kf in enumerate(sorted_kfs):
            if kf.id == segment_start_id:
                start_kf = kf
                for j in range(i + 1, len(sorted_kfs)):
                    if sorted_kfs[j].zoom <= 1.01:
                        end_kf = sorted_kfs[j]
                        break
                break

        pan_points_in_seg = []
        if start_kf:
            for kf in sorted_kfs:
                if (kf.id != segment_start_id
                    and kf.zoom > 1.01
                    and kf.timestamp > start_kf.timestamp
                    and (end_kf is None or kf.timestamp < end_kf.timestamp)):
                    pan_points_in_seg.append(kf)

        pp_number = next(
            (idx + 1 for idx, kf in enumerate(pan_points_in_seg) if kf.id == pan_kf_id),
            0,
        )

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58;"
            "        border-radius: 6px; padding: 4px 0; }"
            "QMenu::item { padding: 6px 16px; }"
            "QMenu::item:selected { background: #8b5cf6; border-radius: 4px; margin: 0 4px; }"
            "QMenu::item:disabled { color: #6c6890; }"
            "QMenu::separator { height: 1px; background: #3d3a58; margin: 4px 8px; }"
        )

        header = menu.addAction(f"Pan point {pp_number}")
        header.setEnabled(False)
        menu.addSeparator()

        # Pick center on preview
        pick_act = menu.addAction("  Pick center on preview\u2026")
        pick_act.setIcon(load_icon("location", color=T.FG_PRIMARY))
        pick_act.triggered.connect(lambda: self._enter_centroid_pick(pan_kf_id))

        # Move earlier / later (reorder)
        if pp_number > 1:
            earlier_act = menu.addAction("⬅  Move earlier")
            prev_kf = pan_points_in_seg[pp_number - 2]
            earlier_act.triggered.connect(
                lambda: self._swap_pan_point_times(pan_kf_id, prev_kf.id)
            )
        if pp_number < len(pan_points_in_seg):
            later_act = menu.addAction("➡  Move later")
            next_kf = pan_points_in_seg[pp_number]
            later_act.triggered.connect(
                lambda: self._swap_pan_point_times(pan_kf_id, next_kf.id)
            )

        menu.addSeparator()
        del_act = menu.addAction("  Delete pan point")
        del_act.setIcon(load_icon("delete", color=T.DANGER))
        del_act.triggered.connect(lambda: self._delete_pan_point(pan_kf_id))

        menu.exec(self.cursor().pos())

    def _swap_pan_point_times(self, kf_id_a: str, kf_id_b: str) -> None:
        """Swap the timestamps of two pan point keyframes to reorder them."""
        self._zoom_engine.push_undo()
        kf_a = kf_b = None
        for kf in self._zoom_engine.keyframes:
            if kf.id == kf_id_a:
                kf_a = kf
            elif kf.id == kf_id_b:
                kf_b = kf
        if kf_a and kf_b:
            kf_a.timestamp, kf_b.timestamp = kf_b.timestamp, kf_a.timestamp
            self._mark_dirty()
            self._zoom_engine.update(self._playback_time)
            self._preview.set_zoom(
                self._zoom_engine.current_zoom,
                self._zoom_engine.current_pan_x,
                self._zoom_engine.current_pan_y,
            )
            self._refresh_editor()

    def _delete_pan_point(self, kf_id: str) -> None:
        """Delete a pan point keyframe and offer to re-place it."""
        # Find the keyframe before deleting, so we can create a replacement
        deleted_kf = None
        for kf in self._zoom_engine.keyframes:
            if kf.id == kf_id:
                deleted_kf = kf
                break
        if deleted_kf is None:
            return

        self._zoom_engine.push_undo()

        # Create a replacement keyframe with a new ID at the same position
        from .models import ZoomKeyframe
        new_kf = ZoomKeyframe.create(
            timestamp=deleted_kf.timestamp,
            zoom=deleted_kf.zoom,
            x=deleted_kf.x,
            y=deleted_kf.y,
            duration=deleted_kf.duration,
            reason=deleted_kf.reason,
            speed=deleted_kf.speed,
        )

        # Remove old, insert new
        self._zoom_engine.keyframes = [
            kf for kf in self._zoom_engine.keyframes if kf.id != kf_id
        ]
        self._zoom_engine.keyframes.append(new_kf)
        self._zoom_engine.keyframes.sort(key=lambda k: k.timestamp)

        self._mark_dirty()
        self._zoom_engine.update(self._playback_time)
        self._preview.set_zoom(
            self._zoom_engine.current_zoom,
            self._zoom_engine.current_pan_x,
            self._zoom_engine.current_pan_y,
        )
        self._refresh_editor()
        self._centroid_target_kf_id = new_kf.id
        self._preview.enter_centroid_pick_mode()
        self._status_text.setText(
            "Click on the preview to set the zoom center. "
            "Press <b>Esc</b> to cancel."
        )
        self._status_dot.setObjectName("StatusDotRecording")
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)

    def _on_centroid_picked(self, pan_x: float, pan_y: float) -> None:
        """Apply the picked centroid to the target keyframe."""
        kf_id = self._centroid_target_kf_id
        self._centroid_target_kf_id = ""
        self._restore_status_bar()
        if not kf_id or pan_x < 0 or pan_y < 0:
            return  # cancelled (Escape) or invalid
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

    def _cancel_centroid_pick(self) -> None:
        """Cancel centroid-pick mode (Escape key or programmatic)."""
        if self._centroid_target_kf_id:
            self._centroid_target_kf_id = ""
            self._preview.cancel_centroid_pick()
            self._restore_status_bar()

    def _restore_status_bar(self) -> None:
        """Reset the status bar to its default state."""
        self._status_text.setText("Ready")
        self._status_dot.setObjectName("StatusDotReady")
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)

    def _on_centroid_dragged(self, kf_id: str, pan_x: float, pan_y: float) -> None:
        """Handle live-dragging of a centroid marker on the debug overlay."""
        for kf in self._zoom_engine.keyframes:
            if kf.id == kf_id:
                # Push undo once at drag start
                if not self._preview._centroid_drag_undo_pushed:
                    self._zoom_engine.push_undo()
                    self._preview._centroid_drag_undo_pushed = True
                kf.x = pan_x
                kf.y = pan_y
                self._mark_dirty()
                break
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

    def _on_preview_pan_point(self, time_ms: float, pan_x: float, pan_y: float) -> None:
        """Handle right-click 'Add pan point here' from preview widget.

        Finds the zoom segment that contains *time_ms* and delegates to
        ``_add_pan_point`` with the clicked position as the pan target.
        """
        sorted_kfs = sorted(self._zoom_engine.keyframes, key=lambda k: k.timestamp)
        for i, kf in enumerate(sorted_kfs):
            if kf.zoom > 1.01:
                # Find segment end
                end_kf = None
                for j in range(i + 1, len(sorted_kfs)):
                    if sorted_kfs[j].zoom <= 1.01:
                        end_kf = sorted_kfs[j]
                        break
                if end_kf and kf.timestamp < time_ms < end_kf.timestamp:
                    self._add_pan_point_at(kf.id, time_ms, pan_x, pan_y)
                    return

    # ── playback / timeline ─────────────────────────────────────────

    def _on_seek(self, time_ms: float) -> None:
        # Clamp to the effective (trimmed) playback range
        eff_start = self._trim_start_ms
        eff_end = self._trim_end_ms if self._trim_end_ms > 0 else self._rec_duration_ms
        time_ms = max(eff_start, min(time_ms, eff_end))

        self._playback_time = time_ms
        # Mark voiceovers whose audio has fully passed as already played.
        # Segments the playhead is currently inside remain unplayed so
        # _check_voiceover_playback can start them from the offset.
        with self._vo_lock:
            self._vo_played_ids = {
                seg.id for seg in self._voiceover_segments
                if (seg.timestamp + (seg.duration_ms if seg.duration_ms > 0 else 5000)) < time_ms
            }
        self._stop_voiceover_audio()
        self._preview.seek_to(time_ms)
        self._preview.set_current_time(time_ms)
        self._editor.set_current_time(time_ms)  # Update editor panel for annotation placement
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
            self._voiceover_segments,
        )

    def _sync_zoom(self) -> None:
        if self._view != "edit":
            self._zoom_sync_timer.stop()
            return
        if self._preview.is_playing:
            t = self._preview.playback_pos_ms
            # Clamp to the effective (trimmed) playback range
            eff_end = self._trim_end_ms if self._trim_end_ms > 0 else self._rec_duration_ms
            if t >= eff_end:
                # Reached the end of the trimmed range — pause playback
                self._preview.pause()
                t = eff_end
                self._timeline.set_playing(False)
                self._stop_voiceover_audio()
            elif self._rec_duration_ms > 0:
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
                self._voiceover_segments,
            )
            # Play voiceover audio at the right time
            self._check_voiceover_playback(t)
        else:
            # Preview may have self-paused (end of video) — sync button state
            self._timeline.set_playing(False)
            self._stop_voiceover_audio()

    # ── save / load ─────────────────────────────────────────────────

    def _save_recording(self) -> None:
        """Export the recording as an H.264 MP4 or GIF via the video exporter."""
        if not self._video_path or not os.path.isfile(self._video_path):
            return
        # Derive default filename from project name if available
        if self._project_path:
            base = os.path.splitext(os.path.basename(self._project_path))[0]
            default_name = f"{base}.mp4"
        else:
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
                self._status_text.setText("Starting export\u2026")
                fps = self._recorder.actual_fps
                if self._actual_fps_override > 0:
                    fps = self._actual_fps_override
                self._ensure_exporter().export(
                    self._video_path, path,
                    self._zoom_engine.keyframes,
                    fps,
                    self._mouse_track,
                    self._monitor_rect,
                    self._bg_preset,
                    self._frame_preset,
                    self._click_events,
                    self._click_preset,
                    self._output_dim,
                    duration_ms=self._rec_duration_ms,
                    frame_timestamps=self._frame_timestamps or None,
                    trim_start_ms=self._trim_start_ms,
                    trim_end_ms=self._trim_end_ms,
                    encoder_id=self._editor.encoder_id,
                    voiceover_segments=self._voiceover_segments or None,
                    video_segments=self._video_segments or None,
                    key_events=self._key_events or None,
                    keystroke_config=self._keystroke_config,
                    annotations=self._annotations,
                    chapters=self._chapters or None,
                )
            except Exception:
                logger.exception("Failed to start export")
                self._title_bar.set_export_text("\u2b06  Export")
                self._title_bar.set_export_enabled(True)
                self._status_text.setText("Export failed to start")

    def _discard_recording(self) -> None:
        """Delete the current recording and return to record mode."""
        if not self._video_path:
            return

        # Confirmation dialog — offer Save when there are unsaved changes
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Discard Recording")
        dlg.setIcon(QMessageBox.Icon.Warning)
        if self._unsaved_changes:
            dlg.setText(
                "Discard this recording and all unsaved changes?\n"
                "This cannot be undone."
            )
            btn_save = dlg.addButton("Save First", QMessageBox.ButtonRole.AcceptRole)
        else:
            dlg.setText(
                "Discard this recording?\nThis cannot be undone."
            )
            btn_save = None
        btn_discard = dlg.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = dlg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        dlg.setDefaultButton(btn_cancel)
        dlg.setStyleSheet("""
            QMessageBox {
                background-color: #1a1829;
                color: #e4e4ed;
            }
            QMessageBox QLabel {
                color: #e4e4ed;
                font-size: 13px;
            }
            QPushButton {
                height: 32px;
                min-width: 80px;
                padding: 0 18px;
                border-radius: 6px;
                border: 1px solid #3d3b55;
                background-color: #28263e;
                color: #e4e4ed;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #353350;
                border-color: #4e4c68;
            }
            QPushButton:default {
                background-color: #8b5cf6;
                border: none;
                color: white;
                font-weight: 600;
            }
            QPushButton:default:hover {
                background-color: #9d74f7;
            }
        """)
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked == btn_cancel:
            return
        if clicked == btn_save:
            self._save_session()
            if self._unsaved_changes:
                return  # user cancelled save dialog

        # Release video handle before deleting (preview holds a cv2.VideoCapture)
        self._preview.stop_playback()

        # Delete the temporary video file
        try:
            if os.path.isfile(self._video_path):
                os.unlink(self._video_path)
                logger.info("Discarded recording: %s", self._video_path)
        except Exception:
            logger.exception("Failed to delete recording file: %s", self._video_path)

        self._video_path = ""
        self._reset_session()
        self._title_bar.set_discard_visible(False)
        self._set_view("record")

    def _on_play_pause(self) -> None:
        if self._preview.is_playing:
            self._preview.pause()
            self._timeline.set_playing(False)
            self._stop_voiceover_audio()
        else:
            # Wrap to trim start if playhead is at/past the effective end
            eff_start = self._trim_start_ms
            eff_end = self._trim_end_ms if self._trim_end_ms > 0 else self._rec_duration_ms
            if self._playback_time >= eff_end - 100:
                self._playback_time = eff_start
                self._preview.seek_to(eff_start)
                self._preview.set_current_time(eff_start)
            # Only mark voiceovers as played if their audio has fully passed
            with self._vo_lock:
                self._vo_played_ids = {
                    seg.id for seg in self._voiceover_segments
                    if (seg.timestamp + (seg.duration_ms if seg.duration_ms > 0 else 5000)) < self._playback_time
                }
            self._preview.play()
            # Only update the button if play actually started
            self._timeline.set_playing(self._preview.is_playing)

    def _check_voiceover_playback(self, t_ms: float) -> None:
        """Play voiceover audio when the playhead reaches a segment's timestamp.

        Also handles mid-segment playback: if the playhead lands inside
        a segment (e.g. after seek or resume), plays from the offset.
        
        Thread-safe: Creates a defensive copy of voiceover segments to avoid
        race conditions during concurrent access.
        """
        import winsound
        # Defensive copy under lock to avoid race conditions with segment updates
        with self._vo_lock:
            segments_snapshot = list(self._voiceover_segments)
        for seg in segments_snapshot:
            with self._vo_lock:
                if seg.id in self._vo_played_ids:
                    continue
            if not seg.audio_path or not os.path.isfile(seg.audio_path):
                continue
            if seg.timestamp > t_ms:
                continue  # not reached yet

            with self._vo_lock:
                self._vo_played_ids.add(seg.id)

            # Calculate how far into the segment we are
            offset_ms = t_ms - seg.timestamp
            seg_end = seg.timestamp + (seg.duration_ms if seg.duration_ms > 0 else 5000)

            if t_ms >= seg_end:
                continue  # playhead is past the end of this segment

            try:
                if offset_ms < 100:
                    # At or near the start — play the whole file
                    winsound.PlaySound(
                        seg.audio_path,
                        winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                    )
                else:
                    # Mid-segment — play from offset
                    self._play_wav_from_offset(seg.audio_path, offset_ms)
            except Exception as exc:
                logger.warning("Could not play voiceover audio: %s", exc)

    def _play_wav_from_offset(self, wav_path: str, offset_ms: float) -> None:
        """Play a WAV file starting from *offset_ms* into the audio."""
        import wave
        import winsound
        import tempfile

        try:
            with wave.open(wav_path, "rb") as wf:
                framerate = wf.getframerate()
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                total_frames = wf.getnframes()

                skip_frames = int(framerate * offset_ms / 1000)
                if skip_frames >= total_frames:
                    return  # nothing left to play

                wf.setpos(skip_frames)
                remaining = wf.readframes(total_frames - skip_frames)

            # Write trimmed audio to a temp file
            tmp = os.path.join(tempfile.gettempdir(), "followcursor_vo_trimmed.wav")
            with wave.open(tmp, "wb") as out:
                out.setnchannels(n_channels)
                out.setsampwidth(sampwidth)
                out.setframerate(framerate)
                out.writeframes(remaining)

            winsound.PlaySound(
                tmp,
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except Exception as exc:
            logger.warning("Could not play trimmed voiceover: %s", exc)

    def _stop_voiceover_audio(self) -> None:
        """Stop any currently playing voiceover audio."""
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

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
            self._zoom_engine.push_undo()
            self._click_events.pop(index)
            self._mark_dirty()
            self._refresh_editor()

    def _on_video_segment_deleted(self, seg_id: str) -> None:
        """Delete a video segment by id (ripple delete).

        At least one segment must remain.  Zoom keyframes within the
        deleted segment's half-open interval [start_ms, end_ms) are
        removed.  Voiceover segments are removed if their time range
        [timestamp, timestamp + duration_ms) overlaps the deleted
        segment at all (partial overlap means the audio would be
        clipped, so the entire voiceover is removed).  All timestamped
        data after the deleted segment is retimed so the remaining
        segments close the gap.
        """
        if len(self._video_segments) <= 1:
            return
        seg = next((s for s in self._video_segments if s.id == seg_id), None)
        if seg is None:
            return
        self._zoom_engine.push_undo()

        gap = seg.end_ms - seg.start_ms  # duration of the removed segment

        # Remove zoom keyframes inside the deleted segment.
        # Use a half-open interval [start_ms, end_ms) so that keyframes exactly
        # at seg.end_ms are preserved and can belong to the following segment.
        self._zoom_engine.keyframes = [
            kf for kf in self._zoom_engine.keyframes
            if not (seg.start_ms <= kf.timestamp < seg.end_ms)
        ]
        # Remove voiceover segments that overlap the deleted segment.
        # A voiceover occupies [v.timestamp, v.timestamp + v.duration_ms).
        # Any overlap with [seg.start_ms, seg.end_ms) means the audio would
        # be partially clipped, so remove the entire voiceover.
        self._voiceover_segments = [
            v for v in self._voiceover_segments
            if not (v.timestamp < seg.end_ms
                    and v.timestamp + v.duration_ms > seg.start_ms)
        ]
        self._zoom_engine.voiceover_segments = self._voiceover_segments

        # Remove the video segment itself
        self._video_segments = [s for s in self._video_segments if s.id != seg_id]

        # ── Ripple: shift everything after the deleted region back by `gap` ──
        # Retime remaining video segments (segments are non-overlapping by design)
        for s in self._video_segments:
            if s.start_ms >= seg.end_ms:
                s.start_ms -= gap
                s.end_ms -= gap

        # Retime zoom keyframes after the deleted region
        for kf in self._zoom_engine.keyframes:
            if kf.timestamp >= seg.end_ms:
                kf.timestamp -= gap

        # Retime voiceover segments after the deleted region
        for v in self._voiceover_segments:
            if v.timestamp >= seg.end_ms:
                v.timestamp -= gap

        # Retime click events after the deleted region
        for ce in self._click_events:
            if ce.timestamp >= seg.end_ms:
                ce.timestamp -= gap

        # Retime key events after the deleted region
        if self._key_events:
            for ke in self._key_events:
                if ke.timestamp >= seg.end_ms:
                    ke.timestamp -= gap

        # Retime mouse track positions after the deleted region
        for mp in self._mouse_track:
            if mp.timestamp >= seg.end_ms:
                mp.timestamp -= gap

        # Retime frame timestamps after the deleted region
        if self._frame_timestamps:
            self._frame_timestamps = [
                t - gap if t >= seg.end_ms else t
                for t in self._frame_timestamps
                if not (seg.start_ms <= t < seg.end_ms)
            ]

        # Adjust recording duration
        self._rec_duration_ms -= gap

        # Adjust trim points
        if self._trim_start_ms >= seg.end_ms:
            self._trim_start_ms -= gap
        elif self._trim_start_ms > seg.start_ms:
            self._trim_start_ms = seg.start_ms
        if self._trim_end_ms > 0:
            if self._trim_end_ms >= seg.end_ms:
                self._trim_end_ms -= gap
            elif self._trim_end_ms > seg.start_ms:
                self._trim_end_ms = seg.start_ms

        self._zoom_engine.video_segments = self._video_segments
        self._mark_dirty()
        self._refresh_editor()

    # ── lazy exporter ───────────────────────────────────────────────

    def _ensure_exporter(self):
        """Lazily import and create the VideoExporter on first use."""
        if self._exporter is None:
            from .video_exporter import VideoExporter
            self._exporter = VideoExporter(parent=self)
            self._exporter.progress.connect(self._on_export_progress)
            self._exporter.finished.connect(self._on_export_finished)
            self._exporter.error.connect(self._on_export_error)
            self._exporter.status.connect(self._on_export_status)
        return self._exporter

    def _connect_exporter_signals_if_ready(self) -> None:
        """No-op — signals are connected lazily in _ensure_exporter."""
        pass

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
            voiceover_segments=list(self._voiceover_segments) if self._voiceover_segments else None,
            video_segments=list(self._video_segments) if self._video_segments else None,
            chapters=list(self._chapters) if self._chapters else None,
        )
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
            # Use metadata-only save when re-saving an existing project
            # (the video is already in the ZIP — no need to rebundle it)
            is_resave = (
                not save_as
                and self._project_path == path
                and os.path.isfile(path)
            )
            self._status_text.setText(
                "Saving metadata\u2026" if is_resave else "Saving project\u2026"
            )
            # Run on background thread so the UI stays responsive
            self._save_worker = _SaveProjectWorker(
                path, self._video_path, session,
                self._monitor_rect, self._recorder.actual_fps,
                self._bg_preset, self._frame_preset, self._click_preset,
                self._keystroke_config,
                self._annotations,
                metadata_only=is_resave,
                parent=self,
            )
            self._save_worker.done.connect(self._on_save_done)
            self._save_worker.failed.connect(self._on_save_failed)
            # Optimistically mark unsaved=False so a quick Ctrl+S
            # doesn't trigger a second save while the worker runs.
            self._project_path = path
            self._unsaved_changes = False
            self._update_title()
            self._title_bar.set_export_text("Saving\u2026")
            self._title_bar.set_export_enabled(False)
            self._btn_save.setEnabled(False)
            self._save_worker.start()

    def _on_save_done(self, path: str) -> None:
        """Background save finished successfully."""
        self._title_bar.set_export_text("\u2b06  Export")
        self._title_bar.set_export_enabled(True)
        self._btn_save.setEnabled(True)
        name = os.path.basename(path)
        self._status_text.setText(
            f'Saved <a href="file:///{path.replace(os.sep, "/")}" '
            f'style="color: #a78bfa; text-decoration: underline;">{name}</a>'
        )
        self._status_text.setOpenExternalLinks(True)
        self._save_worker.deleteLater()
        self._save_worker = None

    def _on_save_failed(self, error: str) -> None:
        """Background save failed."""
        self._title_bar.set_export_text("\u2b06  Export")
        self._title_bar.set_export_enabled(True)
        self._btn_save.setEnabled(True)
        self._unsaved_changes = True
        self._update_title()
        self._status_text.setText(f"Save error: {error}")
        self._save_worker.deleteLater()
        self._save_worker = None

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
            self._mouse_track_timestamps = [mp.timestamp for mp in self._mouse_track]
            self._key_events = session.key_events or []
            self._click_events = session.click_events or []
            self._zoom_engine.click_events = self._click_events
            self._video_segments = list(session.video_segments) if session.video_segments else []
            if not self._video_segments:
                self._video_segments = [VideoSegment.create(start_ms=0.0, end_ms=session.duration)]
            self._zoom_engine.video_segments = self._video_segments
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
            self._zoom_engine.trim_start_ms = session.trim_start_ms
            self._zoom_engine.trim_end_ms = session.trim_end_ms

            # Restore voiceover segments
            self._voiceover_segments = list(session.voiceover_segments) if session.voiceover_segments else []
            self._zoom_engine.voiceover_segments = self._voiceover_segments

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

            # Restore click effect preset if saved
            loaded_click = proj.get("click_preset")
            if loaded_click:
                self._click_preset = loaded_click
                self._preview.set_click_preset(loaded_click)
                self._editor.set_click_preset(loaded_click)

            # Restore keystroke config if saved
            loaded_keystroke = proj.get("keystroke_config")
            if loaded_keystroke:
                self._keystroke_config = loaded_keystroke
                self._editor.set_keystroke_config(loaded_keystroke)

            # Restore annotations if saved
            loaded_annotations = proj.get("annotations")
            if loaded_annotations:
                self._annotations = loaded_annotations
                self._preview.set_annotations(loaded_annotations)
                self._editor.refresh_annotations_list(loaded_annotations)

            # Restore chapters if saved
            if session.chapters:
                self._chapters = list(session.chapters)
                self._timeline.chapters = self._chapters
                self._timeline.update()

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
            dlg.setStyleSheet("""
                QMessageBox {
                    background-color: #1a1829;
                    color: #e4e4ed;
                }
                QMessageBox QLabel {
                    color: #e4e4ed;
                    font-size: 13px;
                }
                QPushButton {
                    height: 32px;
                    min-width: 80px;
                    padding: 0 18px;
                    border-radius: 6px;
                    border: 1px solid #3d3b55;
                    background-color: #28263e;
                    color: #e4e4ed;
                    font-size: 13px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #353350;
                    border-color: #4e4c68;
                }
                QPushButton:default {
                    background-color: #8b5cf6;
                    border: none;
                    color: white;
                    font-weight: 600;
                }
                QPushButton:default:hover {
                    background-color: #9d74f7;
                }
            """)
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

        # Clean up temporary recording file before force-quit
        # (os._exit skips atexit handlers, so we do it explicitly)
        if self._video_path and os.path.isfile(self._video_path):
            try:
                os.remove(self._video_path)
            except OSError:
                pass

        # Clean up project extraction directories
        from .project_file import _cleanup_extract_dirs
        _cleanup_extract_dirs()

        event.accept()
        # Force quit — ensures the process exits even with leftover threads
        import os
        os._exit(0)

    def _restore_geometry(self) -> None:
        """Restore window size/position from saved settings."""
        geom = self._settings.value("windowGeometry")
        if geom and isinstance(geom, QByteArray):
            self.restoreGeometry(geom)
