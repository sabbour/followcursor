"""Right-hand editor panel: zoom settings, smart auto-zoom, background/frame pickers."""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QComboBox,
    QCheckBox,
)

from ..models import ZoomKeyframe, MousePosition, KeyEvent, ClickEvent
from ..activity_analyzer import analyze_activity
from ..backgrounds import (
    PRESETS, DEFAULT_PRESET, BackgroundPreset,
    SOLID_PRESETS, GRADIENT_PRESETS, PATTERN_PRESETS,
    CAT_SOLID, CAT_GRADIENT, CAT_PATTERN, CATEGORY_LABELS,
)
from ..frames import FRAME_PRESETS, DEFAULT_FRAME, FramePreset
from ..utils import (
    fmt_time as _fmt,
    detect_available_encoders as _detect_encoders,
    encoder_display_name as _encoder_name,
    best_hw_encoder as _best_encoder,
)

# Zoom depth presets: label → zoom level
ZOOM_DEPTHS = {
    "Subtle":   1.25,
    "Medium":   1.5,
    "Close":    2.0,
    "Detail":   2.5,
}

# Output dimension presets: label → (width, height) or "auto"
OUTPUT_DIMENSIONS: dict[str, Tuple[int, int] | str] = {
    "Auto (source)":  "auto",
    "16:9  (1920×1080)": (1920, 1080),
    "3:2   (1620×1080)": (1620, 1080),
    "4:3   (1440×1080)": (1440, 1080),
    "1:1   (1080×1080)": (1080, 1080),
    "9:16  (1080×1920)": (1080, 1920),
}

# Autozoom sensitivity presets: label → (max_clusters, min_gap_ms)
SENSITIVITY_PRESETS = {
    "Low":    (3, 6000),
    "Medium": (6, 4000),
    "High":   (10, 2500),
}


class EditorPanel(QWidget):
    """Right-hand sidebar with zoom controls, auto-zoom, background/frame pickers.

    Contains the manual zoom-add button, smart auto-zoom with
    configurable sensitivity and depth, background and device frame
    swatches, output dimension selector, undo/redo buttons, encoder
    selection, and a settings menu with debug overlay toggle.
    """

    remove_keyframe = Signal(str)          # kf id
    add_keyframe_at = Signal(float, float)  # timestamp, zoom
    auto_keyframes_generated = Signal(list)  # list of ZoomKeyframe
    background_changed = Signal(object)     # BackgroundPreset
    frame_changed = Signal(object)          # FramePreset
    debug_overlay_changed = Signal(bool)    # show/hide debug overlay
    output_dimensions_changed = Signal(object)  # (w, h) tuple or "auto"
    undo_requested = Signal()               # undo zoom keyframe change
    redo_requested = Signal()               # redo zoom keyframe change
    encoder_changed = Signal(str)            # encoder_id (e.g. "h264_nvenc")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EditorPanel")
        self.setFixedWidth(280)

        self._container = QVBoxLayout(self)
        self._container.setContentsMargins(16, 20, 16, 16)
        self._container.setSpacing(12)

        self._current_zoom_level = ZOOM_DEPTHS["Subtle"]
        self._trim_start_ms: float = 0.0
        self._trim_end_ms: float = 0.0
        self._duration: float = 0.0

        # ── Add Keyframe ─────────────────────────────────────────────
        manual_title = QLabel("ADD KEYFRAME")
        manual_title.setObjectName("EditorTitle")
        self._container.addWidget(manual_title)

        manual_desc = QLabel("Add a zoom keyframe at the current\nplayback position.")
        manual_desc.setObjectName("Secondary")
        manual_desc.setWordWrap(True)
        self._container.addWidget(manual_desc)

        self._btn_add_zoom = QPushButton("🔍 Add Zoom")
        self._btn_add_zoom.setObjectName("CtrlBtn")
        self._btn_add_zoom.setFixedHeight(32)
        self._btn_add_zoom.setToolTip("Add a zoom-in + auto zoom-out keyframe pair at the current position")
        self._btn_add_zoom.clicked.connect(self._on_manual_zoom_in)
        self._container.addWidget(self._btn_add_zoom)

        # separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #2d2b45; max-height: 1px;")
        self._container.addWidget(sep2)

        # smart zoom
        qa_title = QLabel("SMART ZOOM")
        qa_title.setObjectName("EditorTitle")
        self._container.addWidget(qa_title)

        qa_desc = QLabel("Analyze mouse + click activity to auto-generate\nzoom keyframes at areas of high activity.")
        qa_desc.setObjectName("Secondary")
        qa_desc.setWordWrap(True)
        self._container.addWidget(qa_desc)

        # Sensitivity control
        sens_row = QHBoxLayout()
        sens_row.setSpacing(8)
        sens_label = QLabel("Sensitivity")
        sens_label.setObjectName("Secondary")
        sens_label.setFixedWidth(65)
        sens_row.addWidget(sens_label)

        self._sensitivity_combo = QComboBox()
        self._sensitivity_combo.setObjectName("DepthCombo")
        self._sensitivity_combo.setFixedHeight(30)
        for name in SENSITIVITY_PRESETS:
            self._sensitivity_combo.addItem(name)
        self._sensitivity_combo.setCurrentText("Medium")
        self._sensitivity_combo.setToolTip(
            "Low = fewer zoom keyframes (major activity only)\n"
            "Medium = balanced\n"
            "High = more zoom keyframes (follows smaller movements)"
        )
        sens_row.addWidget(self._sensitivity_combo, 1)
        self._container.addLayout(sens_row)

        activity_btn = QPushButton("✨ Auto-generate zoom keyframes")
        activity_btn.setObjectName("CtrlBtn")
        activity_btn.setFixedHeight(36)
        activity_btn.clicked.connect(self._auto_keyframe)
        self._container.addWidget(activity_btn)

        self._auto_status = QLabel("")
        self._auto_status.setObjectName("Secondary")
        self._auto_status.setWordWrap(True)
        self._auto_status.setVisible(False)
        self._container.addWidget(self._auto_status)

        # separator
        sep_bg = QFrame()
        sep_bg.setFrameShape(QFrame.Shape.HLine)
        sep_bg.setStyleSheet("background-color: #2d2b45; max-height: 1px;")
        self._container.addWidget(sep_bg)

        # ── Background picker ───────────────────────────────────────
        bg_title = QLabel("BACKGROUND")
        bg_title.setObjectName("EditorTitle")
        self._container.addWidget(bg_title)

        # Category combo
        self._bg_category_combo = QComboBox()
        self._bg_category_combo.setObjectName("DepthCombo")
        self._bg_category_combo.setFixedHeight(30)
        for cat_key in (CAT_SOLID, CAT_GRADIENT, CAT_PATTERN):
            self._bg_category_combo.addItem(CATEGORY_LABELS[cat_key], cat_key)
        self._bg_category_combo.currentIndexChanged.connect(self._on_bg_category_changed)
        self._container.addWidget(self._bg_category_combo)

        # Stacked grids — one per category
        from PySide6.QtWidgets import QStackedWidget
        self._bg_stack = QStackedWidget()
        self._bg_buttons: list[QPushButton] = []
        self._bg_category_widgets: dict[str, QWidget] = {}
        for cat_key, cat_presets in (
            (CAT_SOLID, SOLID_PRESETS),
            (CAT_GRADIENT, GRADIENT_PRESETS),
            (CAT_PATTERN, PATTERN_PRESETS),
        ):
            page = QWidget()
            page.setStyleSheet("background: transparent;")
            grid = self._build_bg_grid(cat_presets, cat_key)
            page.setLayout(grid)
            self._bg_stack.addWidget(page)
            self._bg_category_widgets[cat_key] = page
        self._container.addWidget(self._bg_stack)

        self._current_bg_preset = DEFAULT_PRESET

        # separator
        sep_fr = QFrame()
        sep_fr.setFrameShape(QFrame.Shape.HLine)
        sep_fr.setStyleSheet("background-color: #2d2b45; max-height: 1px;")
        self._container.addWidget(sep_fr)

        # ── Frame picker ─────────────────────────────────────────
        fr_title = QLabel("DEVICE FRAME")
        fr_title.setObjectName("EditorTitle")
        self._container.addWidget(fr_title)

        self._frame_combo = QComboBox()
        self._frame_combo.setObjectName("DepthCombo")
        self._frame_combo.setFixedHeight(30)
        for fp in FRAME_PRESETS:
            self._frame_combo.addItem(fp.name)
        self._frame_combo.setCurrentText(DEFAULT_FRAME.name)
        self._frame_combo.currentTextChanged.connect(self._on_frame_changed)
        self._container.addWidget(self._frame_combo)

        self._current_frame_preset = DEFAULT_FRAME

        # separator
        sep_dim = QFrame()
        sep_dim.setFrameShape(QFrame.Shape.HLine)
        sep_dim.setStyleSheet("background-color: #2d2b45; max-height: 1px;")
        self._container.addWidget(sep_dim)

        # ── Output dimensions picker ────────────────────────────────
        dim_title = QLabel("OUTPUT SIZE")
        dim_title.setObjectName("EditorTitle")
        self._container.addWidget(dim_title)

        self._dim_combo = QComboBox()
        self._dim_combo.setObjectName("DepthCombo")
        self._dim_combo.setFixedHeight(30)
        for name in OUTPUT_DIMENSIONS:
            self._dim_combo.addItem(name)
        self._dim_combo.setCurrentText("Auto (source)")
        self._dim_combo.currentTextChanged.connect(self._on_dim_changed)
        self._dim_combo.setToolTip(
            "Choose the aspect ratio and resolution for the exported video.\n"
            "Auto = same dimensions as the recorded source."
        )
        self._container.addWidget(self._dim_combo)

        self._current_output_dim = "auto"

        # ── Session info (compact, at the bottom) ───────────────────
        self._container.addStretch()

        # Undo / Redo row
        undo_redo_row = QHBoxLayout()
        undo_redo_row.setSpacing(4)
        self._btn_undo = QPushButton("↩ Undo")
        self._btn_undo.setObjectName("CtrlBtn")
        self._btn_undo.setFixedHeight(28)
        self._btn_undo.setToolTip("Undo last zoom change (Ctrl+Z)")
        self._btn_undo.clicked.connect(self.undo_requested.emit)
        undo_redo_row.addWidget(self._btn_undo)

        self._btn_redo = QPushButton("Redo ↪")
        self._btn_redo.setObjectName("CtrlBtn")
        self._btn_redo.setFixedHeight(28)
        self._btn_redo.setToolTip("Redo last undone change (Ctrl+Y)")
        self._btn_redo.clicked.connect(self.redo_requested.emit)
        undo_redo_row.addWidget(self._btn_redo)
        self._container.addLayout(undo_redo_row)

        # Info + settings row
        info_row = QHBoxLayout()
        info_row.setSpacing(6)

        self._info_label = QLabel("ℹ️")
        self._info_label.setObjectName("Secondary")
        self._info_label.setToolTip("Duration: 0:00\nMouse samples: 0\nKeyframes: 0")
        self._info_label.setCursor(Qt.CursorShape.WhatsThisCursor)
        self._info_label.setStyleSheet(
            "QLabel { color: #6c6890; font-size: 13px; padding: 4px 0; }"
            "QToolTip { background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58; padding: 6px; }"
        )
        info_row.addWidget(self._info_label)

        info_row.addStretch()

        self._btn_settings = QPushButton("⚙")
        self._btn_settings.setObjectName("CtrlBtn")
        self._btn_settings.setFixedSize(28, 28)
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_settings.clicked.connect(self._show_settings_menu)
        info_row.addWidget(self._btn_settings)

        self._container.addLayout(info_row)

        # Debug overlay state (managed via settings menu)
        self._debug_overlay_enabled = False

        # Encoder preference (auto-detected best available)
        self._encoder_id: str = _best_encoder()

        self._mouse_track: List[MousePosition] = []
        self._key_events: List[KeyEvent] = []
        self._click_events: List[ClickEvent] = []
        self._monitor_rect: dict = {}

    # ── position / depth controls ───────────────────────────────────

    def _show_settings_menu(self) -> None:
        """Show settings popup menu from the cog button."""
        from PySide6.QtWidgets import QMenu, QWidgetAction
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #28263e; color: #e4e4ed; border: 1px solid #3d3a58; padding: 4px; }"
            "QMenu::item { padding: 6px 20px; }"
            "QMenu::item:selected { background: #8b5cf6; }"
        )

        # Debug overlay toggle
        check_text = "✓ " if self._debug_overlay_enabled else "  "
        debug_act = menu.addAction(f"{check_text}Show zoom debug overlay")
        debug_act.setToolTip(
            "Overlay colored markers on the preview showing\n"
            "where activity was detected and why zoom\n"
            "keyframes were placed."
        )
        debug_act.triggered.connect(self._toggle_debug_overlay)

        # Encoder submenu
        encoder_menu = menu.addMenu("Video encoder")
        encoder_menu.setStyleSheet(menu.styleSheet())
        available = _detect_encoders()
        for enc_id in available:
            label = _encoder_name(enc_id)
            tick = "✓ " if enc_id == self._encoder_id else "  "
            act = encoder_menu.addAction(f"{tick}{label}")
            act.setData(enc_id)
            act.triggered.connect(lambda checked=False, eid=enc_id: self._set_encoder(eid))

        menu.exec(self._btn_settings.mapToGlobal(self._btn_settings.rect().topRight()))

    def _set_encoder(self, enc_id: str) -> None:
        """Update the selected encoder and emit signal."""
        self._encoder_id = enc_id
        self.encoder_changed.emit(enc_id)
        logger.info("Encoder set to: %s", _encoder_name(enc_id))

    @property
    def encoder_id(self) -> str:
        """The currently selected ffmpeg encoder ID."""
        return self._encoder_id

    def set_encoder_by_id(self, enc_id: str) -> None:
        """Programmatically set the encoder (e.g. from QSettings)."""
        self._encoder_id = enc_id

    def _toggle_debug_overlay(self) -> None:
        """Toggle the debug overlay state and emit the signal."""
        self._debug_overlay_enabled = not self._debug_overlay_enabled
        self.debug_overlay_changed.emit(self._debug_overlay_enabled)

    def _on_dim_changed(self, text: str) -> None:
        dim = OUTPUT_DIMENSIONS.get(text, "auto")
        self._current_output_dim = dim
        self.output_dimensions_changed.emit(dim)

    def _on_manual_zoom_in(self) -> None:
        self.add_keyframe_at.emit(-1.0, self._current_zoom_level)

    @property
    def zoom_level(self) -> float:
        return self._current_zoom_level

    @property
    def follow_cursor(self) -> bool:
        return True

    @property
    def bg_preset(self) -> BackgroundPreset:
        return self._current_bg_preset

    @property
    def frame_preset(self) -> FramePreset:
        return self._current_frame_preset

    @property
    def output_dim(self):
        """Return the currently selected output dimensions: (w, h) tuple or 'auto'."""
        return self._current_output_dim

    def _on_frame_changed(self, text: str) -> None:
        fp = next((f for f in FRAME_PRESETS if f.name == text), DEFAULT_FRAME)
        self._current_frame_preset = fp
        self.frame_changed.emit(fp)

    def set_background_by_name(self, name: str) -> None:
        """Programmatically select a background preset by name."""
        preset = next((p for p in PRESETS if p.name == name), None)
        if preset is None:
            return
        self._current_bg_preset = preset
        # Switch combo to the correct category page
        cat_index = {CAT_SOLID: 0, CAT_GRADIENT: 1, CAT_PATTERN: 2}.get(
            preset.category, 0
        )
        self._bg_category_combo.setCurrentIndex(cat_index)
        # Highlight the matching swatch button
        for btn in self._bg_buttons:
            if btn.toolTip() == name:
                self._highlight_bg_button(btn)
                break

    def set_frame_by_name(self, name: str) -> None:
        """Programmatically select a frame preset by name."""
        self._frame_combo.setCurrentText(name)

    # ── background picker ───────────────────────────────────────────

    def _on_bg_category_changed(self, index: int) -> None:
        """Switch the visible swatch grid when the category combo changes."""
        self._bg_stack.setCurrentIndex(index)

    def _build_bg_grid(self, presets: list, category: str):
        """Build a grid of colour-swatch buttons for one category."""
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(5)
        grid.setContentsMargins(0, 4, 0, 4)

        # Patterns get larger, fewer-per-row swatches so the pattern is visible
        if category == CAT_PATTERN:
            size, cols = 32, 7
        elif category == CAT_GRADIENT:
            size, cols = 28, 8
        else:
            size, cols = 24, 9

        for idx, preset in enumerate(presets):
            btn = QPushButton()
            btn.setFixedSize(size, size)
            btn.setToolTip(preset.name)
            btn.setStyleSheet(self._bg_swatch_css(preset, "transparent"))
            btn.clicked.connect(
                lambda checked, p=preset, b=btn: self._on_bg_selected(p, b)
            )
            grid.addWidget(btn, idx // cols, idx % cols)
            self._bg_buttons.append(btn)
        return grid

    def _on_bg_selected(self, preset: BackgroundPreset, btn: QPushButton) -> None:
        self._current_bg_preset = preset
        self._highlight_bg_button(btn)
        self.background_changed.emit(preset)

    def _highlight_bg_button(self, active_btn: QPushButton) -> None:
        """Update border highlight on the selected swatch."""
        for btn in self._bg_buttons:
            tip = btn.toolTip()
            preset = next((p for p in PRESETS if p.name == tip), None)
            if preset is None:
                continue
            is_active = btn is active_btn
            border = "#a78bfa" if is_active else "transparent"
            btn.setStyleSheet(self._bg_swatch_css(preset, border))

    @staticmethod
    def _bg_swatch_css(preset: BackgroundPreset, border: str) -> str:
        """Return QSS for a background swatch button."""
        r1, g1, b1 = preset.color_top
        r2, g2, b2 = preset.color_bottom
        kind = preset.kind

        if kind == "wavy":
            # Diagonal gradient to hint at waves
            mr, mg, mb = (r1+r2)//2, (g1+g2)//2, (b1+b2)//2
            return (
                f"QPushButton {{ background: qlineargradient("
                f"x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:0.5 rgb({mr},{mg},{mb}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: 6px; }}"
                f"QPushButton:hover {{ border-color: #8b5cf6; }}"
            )
        elif kind == "radial":
            # Radial uses a circular feel — approximate with 4-stop gradient
            return (
                f"QPushButton {{ background: qradialgradient("
                f"cx:0.5, cy:0.5, radius:0.7, fx:0.5, fy:0.5, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: 6px; }}"
                f"QPushButton:hover {{ border-color: #8b5cf6; }}"
            )
        elif kind == "spotlight":
            # Off-centre radial glow
            return (
                f"QPushButton {{ background: qradialgradient("
                f"cx:0.8, cy:0.2, radius:0.9, fx:0.8, fy:0.2, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: 6px; }}"
                f"QPushButton:hover {{ border-color: #8b5cf6; }}"
            )
        elif kind == "diagonal":
            # Repeating stripe look
            return (
                f"QPushButton {{ background: qlineargradient("
                f"x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:0.25 rgb({r2},{g2},{b2}), "
                f"stop:0.5 rgb({r1},{g1},{b1}), "
                f"stop:0.75 rgb({r2},{g2},{b2}), "
                f"stop:1 rgb({r1},{g1},{b1})); "
                f"border: 2px solid {border}; border-radius: 6px; }}"
                f"QPushButton:hover {{ border-color: #8b5cf6; }}"
            )
        elif kind == "dots":
            # Radial hint on dark bg
            return (
                f"QPushButton {{ background: qradialgradient("
                f"cx:0.3, cy:0.3, radius:0.4, fx:0.3, fy:0.3, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: 6px; }}"
                f"QPushButton:hover {{ border-color: #8b5cf6; }}"
            )
        elif kind == "chevron":
            # Zigzag hint with 5 alternating stops
            mr, mg, mb = (r1+r2)//2, (g1+g2)//2, (b1+b2)//2
            return (
                f"QPushButton {{ background: qlineargradient("
                f"x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 rgb({r2},{g2},{b2}), "
                f"stop:0.3 rgb({r1},{g1},{b1}), "
                f"stop:0.5 rgb({r2},{g2},{b2}), "
                f"stop:0.7 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: 6px; }}"
                f"QPushButton:hover {{ border-color: #8b5cf6; }}"
            )
        elif kind == "rings":
            # Concentric hint
            return (
                f"QPushButton {{ background: qradialgradient("
                f"cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, "
                f"stop:0 rgb({r2},{g2},{b2}), "
                f"stop:0.4 rgb({r1},{g1},{b1}), "
                f"stop:0.6 rgb({r2},{g2},{b2}), "
                f"stop:0.8 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: 6px; }}"
                f"QPushButton:hover {{ border-color: #8b5cf6; }}"
            )
        elif kind == "gradient":
            return (
                f"QPushButton {{ background: qlineargradient("
                f"x1:0, y1:0, x2:0, y2:1, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: 6px; }}"
                f"QPushButton:hover {{ border-color: #8b5cf6; }}"
            )
        else:  # solid
            return (
                f"QPushButton {{ background: rgb({r1},{g1},{b1}); "
                f"border: 2px solid {border}; border-radius: 6px; }}"
                f"QPushButton:hover {{ border-color: #8b5cf6; }}"
            )

    # ── public ──────────────────────────────────────────────────────

    def refresh(
        self,
        keyframes: List[ZoomKeyframe],
        mouse_track: List[MousePosition],
        duration: float,
        monitor_rect: dict | None = None,
        key_events: List[KeyEvent] | None = None,
        click_events: List[ClickEvent] | None = None,
        trim_start_ms: float = 0.0,
        trim_end_ms: float = 0.0,
    ) -> None:
        """Update cached session data used by auto-zoom and the info tooltip."""
        self._mouse_track = mouse_track
        self._key_events = key_events or []
        self._click_events = click_events or []
        self._duration = duration
        self._trim_start_ms = trim_start_ms
        self._trim_end_ms = trim_end_ms
        if monitor_rect is not None:
            self._monitor_rect = monitor_rect

        self._info_label.setToolTip(
            f"Duration: {_fmt(duration)}\n"
            f"Mouse samples: {len(mouse_track):,}\n"
            f"Keyframes: {len(keyframes)}"
        )

    def _auto_keyframe(self) -> None:
        track = self._mouse_track

        # Apply trim range: only analyze data within the trimmed window
        t_start = self._trim_start_ms
        t_end = self._trim_end_ms if self._trim_end_ms > 0 else self._duration
        if t_start > 0 or (self._trim_end_ms > 0 and t_end < self._duration):
            track = [m for m in track if t_start <= m.timestamp <= t_end]
            filtered_keys: list = [
                KeyEvent(timestamp=k.timestamp)
                for k in self._key_events if t_start <= k.timestamp <= t_end
            ]
            filtered_clicks: list = [
                ClickEvent(timestamp=c.timestamp, x=c.x, y=c.y)
                for c in self._click_events if t_start <= c.timestamp <= t_end
            ]
        else:
            filtered_keys = list(self._key_events)
            filtered_clicks = list(self._click_events)

        if len(track) < 10:
            self._auto_status.setText("Not enough mouse data to analyze.")
            self._auto_status.setVisible(True)
            return
        if not self._monitor_rect:
            self._auto_status.setText("No monitor info available.")
            self._auto_status.setVisible(True)
            return

        # Get sensitivity settings
        sens_name = self._sensitivity_combo.currentText()
        max_clusters, min_gap = SENSITIVITY_PRESETS.get(sens_name, (6, 4000))

        try:
            keyframes = analyze_activity(
                track, self._monitor_rect,
                key_events=filtered_keys or None,
                click_events=filtered_clicks or None,
                zoom_level=self._current_zoom_level,
                follow_cursor=self.follow_cursor,
                max_clusters=max_clusters,
                min_gap_ms=min_gap,
            )
        except Exception as exc:
            self._auto_status.setText(f"Analysis error: {exc}")
            self._auto_status.setVisible(True)
            return

        if not keyframes:
            self._auto_status.setText("No significant activity clusters detected.")
            self._auto_status.setVisible(True)
            return

        # Count actual zoom-in keyframes (zoom > 1.0) as the cluster count
        n_clusters = sum(1 for kf in keyframes if kf.zoom > 1.0 and not kf.reason.startswith("Pan to:"))
        self._auto_status.setText(
            f"Generated {len(keyframes)} keyframes from {n_clusters} activity cluster{'s' if n_clusters != 1 else ''}."
        )
        self._auto_status.setVisible(True)
        self.auto_keyframes_generated.emit(keyframes)
