"""Right-hand editor panel: zoom settings, smart auto-zoom, background/frame pickers."""

import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QStyle,
)

from .. import tokens as T
from ..fluent_effects import apply_shadow, install_focus_ring
from ..fluent_tab_bar import FluentTabBar
from ..icon_loader import load_icon
from ..models import ZoomKeyframe, MousePosition, KeyEvent, ClickEvent, ClickEffectPreset, CLICK_EFFECT_PRESETS, DEFAULT_CLICK_EFFECT
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

# TTS voice options
# TTS voice cache (populated from Azure Speech Service on first settings save)
_cached_voices: list[str] = []


class _CollapsibleSection(QWidget):
    """A section header that toggles visibility of its body widget."""

    expanded = Signal()

    def __init__(self, title: str, body: QWidget, collapsed: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self._btn = QPushButton()
        self._btn.setObjectName("InspectorSectionHeader")
        self._btn.setFixedHeight(32)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._toggle)
        layout.addWidget(self._btn)

        self._body = body
        layout.addWidget(body)

        self._title = title
        self._collapsed = collapsed
        body.setVisible(not collapsed)
        self._update_text()

    def _toggle(self) -> None:
        self.set_collapsed(not self._collapsed)
        if not self._collapsed:
            self.expanded.emit()

    def set_collapsed(self, collapsed: bool) -> None:
        """Set the disclosure state without emitting an interaction signal."""
        self._collapsed = collapsed
        self._body.setVisible(not collapsed)
        self._update_text()

    def _update_text(self) -> None:
        icon_role = (
            QStyle.StandardPixmap.SP_ArrowRight
            if self._collapsed
            else QStyle.StandardPixmap.SP_ArrowDown
        )
        self._btn.setProperty("collapsed", self._collapsed)
        self._btn.setIcon(self.style().standardIcon(icon_role))
        self._btn.setText(self._title)


class _StatusLabel(QLabel):
    """Single-line inspector feedback that preserves full text in its tooltip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setObjectName("InspectorStatus")
        self.setMinimumWidth(0)
        self.setMaximumWidth(320 - (2 * T.SPACE_LG))
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setVisible(False)

    def set_status(self, text: str) -> None:
        """Show compact feedback while retaining the complete message."""
        self._full_text = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        self.setVisible(bool(text))
        self._update_elided_text()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        available_width = max(0, self.contentsRect().width())
        self.setText(
            self.fontMetrics().elidedText(
                self._full_text,
                Qt.TextElideMode.ElideRight,
                available_width,
            )
        )


class _AISettingsDialog(QDialog):
    """Modal dialog for configuring Azure AI Foundry API credentials."""

    def __init__(self, current_settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Settings — Azure AI Foundry")
        self.setMinimumWidth(420)
        self.setStyleSheet(
            f"QDialog {{ background: {T.BG_SURFACE}; }}"
            f"QLabel {{ color: {T.FG_PRIMARY}; font-size: {T.FONT_SIZE_BODY}px; }}"
            f"QLineEdit {{ background: {T.BG_INTERACTIVE}; color: {T.FG_PRIMARY};"
            f"  border: 1px solid {T.CARD_BORDER};"
            f"  border-radius: {T.RADIUS_SMALL}px; padding: 6px;"
            f"  font-size: {T.FONT_SIZE_BODY}px; }}"
            f"QComboBox {{ background: {T.BG_INTERACTIVE}; color: {T.FG_PRIMARY};"
            f"  border: 1px solid {T.CARD_BORDER};"
            f"  border-radius: {T.RADIUS_SMALL}px; padding: {T.SPACE_XXS}px {T.SPACE_XS}px;"
            f"  font-size: {T.FONT_SIZE_BODY}px; }}"
            f"QPushButton {{ background: {T.BG_INTERACTIVE}; color: {T.FG_PRIMARY};"
            f"  border: 1px solid {T.CARD_BORDER};"
            f"  border-radius: {T.RADIUS_SMALL}px; padding: 6px {T.SPACE_MD}px;"
            f"  min-width: 80px; }}"
            f"QPushButton:hover {{ background: {T.BRAND}; }}"
        )

        # Fluent 2 — medium shadow on floating dialog
        apply_shadow(self, level="medium")

        layout = QVBoxLayout(self)
        layout.setSpacing(T.SPACE_MD)

        info = QLabel(
            "Configure your Azure AI Foundry credentials.\n"
            "Chat model is used for AI Smart Zoom.\n"
            "Automated narration always runs on GPT-5.4 and feeds the normal voiceover flow.\n"
            "TTS uses Azure Speech Service with the same key."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {T.FG_SECONDARY}; font-size: 12px;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(T.SPACE_SM)

        self._endpoint = QLineEdit(current_settings.endpoint)
        self._endpoint.setPlaceholderText("https://models.inference.ai.azure.com")
        form.addRow("Endpoint:", self._endpoint)

        self._api_key = QLineEdit(current_settings.api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setPlaceholderText("Your API key or token")
        form.addRow("API Key:", self._api_key)

        self._chat_model = QLineEdit(current_settings.chat_model)
        self._chat_model.setPlaceholderText("e.g. gpt-4o-mini (Smart Zoom)")
        form.addRow("Chat Model:", self._chat_model)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Fluent 2 — focus rings on dialog input fields
        for child in self.findChildren(QLineEdit):
            install_focus_ring(child)

    def get_settings(self):
        from ..ai_service import AISettings
        return AISettings(
            endpoint=self._endpoint.text().strip(),
            api_key=self._api_key.text().strip(),
            chat_model=self._chat_model.text().strip(),
            narration_model="gpt-5.4",
        )


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
    click_effect_changed = Signal(object)   # ClickEffectPreset
    debug_overlay_changed = Signal(bool)    # show/hide debug overlay
    output_dimensions_changed = Signal(object)  # (w, h) tuple or "auto"
    undo_requested = Signal()               # undo zoom keyframe change
    redo_requested = Signal()               # redo zoom keyframe change
    encoder_changed = Signal(str)            # encoder_id (e.g. "h264_nvenc")
    # AI feature signals
    ai_zoom_requested = Signal(int, float, int)  # max_clusters, zoom_level, min_gap_ms
    generate_narration_requested = Signal(str, str)  # default voice name, guidance prompt
    add_voiceover_requested = Signal(float, str)  # timestamp_ms, voice
    ai_settings_changed = Signal()               # settings were updated
    auto_detect_chapters_requested = Signal()   # deprecated compatibility signal
    generate_chapters_requested = Signal()      # request AI chapter generation
    chapter_added = Signal(object)               # Chapter object
    chapter_removed = Signal(int)                # chapter timestamp_ms

    @staticmethod
    def _add_tab(tabs: QTabWidget, title: str) -> QVBoxLayout:
        """Add a scrollable inspector tab and return its content layout."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        container = QVBoxLayout(content)
        container.setContentsMargins(0, T.SPACE_SM, 0, T.SPACE_SM)
        container.setSpacing(T.SPACE_SM)
        scroll.setWidget(content)
        page_layout.addWidget(scroll)
        tabs.addTab(page, title)
        return container

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EditorPanel")
        self.setFixedWidth(320)

        # Outer layout: task-focused inspector tabs + fixed bottom bar
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("InspectorTabs")
        tab_bar = FluentTabBar()
        tab_bar.setExpanding(True)
        self._tabs.setTabBar(tab_bar)
        self._motion_container = self._add_tab(self._tabs, "Motion")
        self._style_container = self._add_tab(self._tabs, "Style")
        self._audio_container = self._add_tab(self._tabs, "Audio")
        self._tabs.setTabToolTip(0, "Zoom and camera movement")
        self._tabs.setTabToolTip(1, "Background, frame, click effects, and output size")
        self._tabs.setTabToolTip(2, "Chapters, narration, and voiceover")
        outer.addWidget(self._tabs, 1)

        self._current_zoom_level = ZOOM_DEPTHS["Medium"]
        self._trim_start_ms: float = 0.0
        self._trim_end_ms: float = 0.0
        self._duration: float = 0.0

        # ── Smart Zoom (collapsible) ─────────────────────────────────
        zoom_body = QWidget()
        zoom_lay = QVBoxLayout(zoom_body)
        zoom_lay.setContentsMargins(T.SPACE_LG, T.SPACE_MD, T.SPACE_LG, T.SPACE_SM)
        zoom_lay.setSpacing(T.SPACE_SM)

        sens_row = QHBoxLayout()
        sens_row.setSpacing(T.SPACE_SM)
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
        zoom_lay.addLayout(sens_row)

        zoom_actions = QHBoxLayout()
        zoom_actions.setSpacing(T.SPACE_SM)

        activity_btn = QPushButton("Local")
        activity_btn.setObjectName("InspectorPrimaryAction")
        activity_btn.setFixedHeight(32)
        activity_btn.setAccessibleName("Generate zoom locally")
        activity_btn.setToolTip("Generate camera moves from recorded activity on this device.")
        activity_btn.clicked.connect(self._auto_keyframe)
        zoom_actions.addWidget(activity_btn, 1)

        ai_zoom_btn = QPushButton("AI")
        ai_zoom_btn.setObjectName("CtrlBtn")
        ai_zoom_btn.setFixedHeight(32)
        ai_zoom_btn.setAccessibleName("Generate zoom with AI")
        ai_zoom_btn.setToolTip("Use AI (Azure AI Foundry) to analyze activity\nand generate zoom keyframes.")
        ai_zoom_btn.clicked.connect(self._on_ai_zoom)
        zoom_actions.addWidget(ai_zoom_btn, 1)
        zoom_lay.addLayout(zoom_actions)
        self._btn_ai_zoom = ai_zoom_btn

        self._zoom_status = _StatusLabel()
        self._auto_status = self._zoom_status
        self._ai_zoom_status = self._zoom_status
        zoom_lay.addWidget(self._zoom_status)

        self._motion_container.addWidget(_CollapsibleSection("SMART ZOOM", zoom_body))

        # ── Chapters (collapsible) ───────────────────────────────────
        chapters_body = QWidget()
        chapters_lay = QVBoxLayout(chapters_body)
        chapters_lay.setContentsMargins(T.SPACE_LG, T.SPACE_MD, T.SPACE_LG, T.SPACE_SM)
        chapters_lay.setSpacing(T.SPACE_SM)

        chapters_desc = QLabel("Build markers automatically or add one at the playhead.")
        chapters_desc.setObjectName("Secondary")
        chapters_desc.setWordWrap(True)
        chapters_lay.addWidget(chapters_desc)

        chapter_actions = QHBoxLayout()
        chapter_actions.setSpacing(T.SPACE_SM)

        self._btn_generate_chapters = QPushButton("Generate")
        self._btn_generate_chapters.setObjectName("InspectorPrimaryAction")
        self._btn_generate_chapters.setFixedHeight(32)
        self._btn_generate_chapters.setToolTip(
            "Use GPT-5.4 to suggest chapter markers from the same shared recording context\n"
            "as narration. Re-running replaces only generated chapters and keeps manual markers."
        )
        self._btn_generate_chapters.clicked.connect(self._on_generate_chapters)
        chapter_actions.addWidget(self._btn_generate_chapters, 1)

        self._btn_add_chapter = QPushButton("Add here")
        self._btn_add_chapter.setObjectName("CtrlBtn")
        self._btn_add_chapter.setFixedHeight(32)
        self._btn_add_chapter.setAccessibleName("Add chapter at playhead")
        self._btn_add_chapter.setToolTip("Add a chapter marker at the current playback position.")
        self._btn_add_chapter.clicked.connect(self._on_add_chapter)
        chapter_actions.addWidget(self._btn_add_chapter, 1)
        chapters_lay.addLayout(chapter_actions)

        self._chapters_status = _StatusLabel()
        chapters_lay.addWidget(self._chapters_status)

        chapters_section = _CollapsibleSection("CHAPTERS", chapters_body, collapsed=True)
        self._audio_container.addWidget(chapters_section)

        # ── Voiceover (collapsible) ──────────────────────────────────
        vo_body = QWidget()
        vo_lay = QVBoxLayout(vo_body)
        vo_lay.setContentsMargins(T.SPACE_LG, T.SPACE_MD, T.SPACE_LG, T.SPACE_SM)
        vo_lay.setSpacing(T.SPACE_SM)

        vo_desc = QLabel("Generate a full script or add a voiceover at the playhead.")
        vo_desc.setObjectName("Secondary")
        vo_desc.setWordWrap(True)
        vo_lay.addWidget(vo_desc)

        vo_guidance_label = QLabel("Optional guidance")
        vo_guidance_label.setObjectName("Secondary")
        vo_lay.addWidget(vo_guidance_label)

        self._narration_guidance = QPlainTextEdit()
        self._narration_guidance.setObjectName("NarrationGuidance")
        self._narration_guidance.setPlaceholderText(
            "For example: Lead with the time saved."
        )
        self._narration_guidance.setFixedHeight(52)
        vo_lay.addWidget(self._narration_guidance)

        voice_actions = QHBoxLayout()
        voice_actions.setSpacing(T.SPACE_SM)

        self._btn_generate_narration = QPushButton("Generate")
        self._btn_generate_narration.setObjectName("InspectorPrimaryAction")
        self._btn_generate_narration.setFixedHeight(32)
        self._btn_generate_narration.setToolTip(
            "Use GPT-5.4 to draft five presentation-style voiceover segments,\n"
            "keep the wording focused on what matters rather than on-screen mechanics,\n"
            "save the combined script beside the recording, then start speech automatically through the normal voiceover flow.\n"
            "Open any generated segment to review the spoken line, then drag or delete it like any other voiceover."
        )
        self._btn_generate_narration.clicked.connect(self._on_generate_narration)
        voice_actions.addWidget(self._btn_generate_narration, 1)

        self._btn_add_voiceover = QPushButton("Add here")
        self._btn_add_voiceover.setObjectName("CtrlBtn")
        self._btn_add_voiceover.setFixedHeight(32)
        self._btn_add_voiceover.setAccessibleName("Add voiceover at playhead")
        self._btn_add_voiceover.setToolTip(
            "Add a manual text-to-speech voiceover segment at the current playback position.\n"
            "Use the Voice track to review, drag, or delete it later."
        )
        self._btn_add_voiceover.clicked.connect(self._on_add_voiceover)
        voice_actions.addWidget(self._btn_add_voiceover, 1)
        vo_lay.addLayout(voice_actions)

        self._narration_status = _StatusLabel()
        self._vo_status = _StatusLabel()
        vo_lay.addWidget(self._narration_status)
        vo_lay.addWidget(self._vo_status)

        voice_section = _CollapsibleSection("VOICEOVER", vo_body)
        self._audio_container.addWidget(voice_section)
        self._connect_exclusive_sections([chapters_section, voice_section])

        # ── Background picker (collapsible) ──────────────────────────
        bg_body = QWidget()
        bg_lay = QVBoxLayout(bg_body)
        bg_lay.setContentsMargins(T.SPACE_LG, T.SPACE_MD, T.SPACE_LG, T.SPACE_SM)
        bg_lay.setSpacing(T.SPACE_SM)

        self._bg_category_combo = QComboBox()
        self._bg_category_combo.setObjectName("DepthCombo")
        self._bg_category_combo.setFixedHeight(30)
        for cat_key in (CAT_SOLID, CAT_GRADIENT, CAT_PATTERN):
            self._bg_category_combo.addItem(CATEGORY_LABELS[cat_key], cat_key)
        self._bg_category_combo.currentIndexChanged.connect(self._on_bg_category_changed)
        bg_lay.addWidget(self._bg_category_combo)

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
        bg_lay.addWidget(self._bg_stack)
        self._current_bg_preset = DEFAULT_PRESET

        background_section = _CollapsibleSection("BACKGROUND", bg_body, collapsed=True)
        self._style_container.addWidget(background_section)

        # ── Frame picker (collapsible) ───────────────────────────────
        fr_body = QWidget()
        fr_lay = QVBoxLayout(fr_body)
        fr_lay.setContentsMargins(T.SPACE_LG, T.SPACE_MD, T.SPACE_LG, T.SPACE_SM)
        fr_lay.setSpacing(T.SPACE_SM)

        self._frame_combo = QComboBox()
        self._frame_combo.setObjectName("DepthCombo")
        self._frame_combo.setFixedHeight(30)
        for fp in FRAME_PRESETS:
            self._frame_combo.addItem(fp.name)
        self._frame_combo.setCurrentText(DEFAULT_FRAME.name)
        self._frame_combo.currentTextChanged.connect(self._on_frame_changed)
        fr_lay.addWidget(self._frame_combo)
        self._current_frame_preset = DEFAULT_FRAME

        frame_section = _CollapsibleSection("DEVICE FRAME", fr_body, collapsed=True)
        self._style_container.addWidget(frame_section)

        # ── Click effect picker (collapsible) ────────────────────────
        click_body = QWidget()
        click_lay = QVBoxLayout(click_body)
        click_lay.setContentsMargins(T.SPACE_LG, T.SPACE_MD, T.SPACE_LG, T.SPACE_SM)
        click_lay.setSpacing(T.SPACE_SM)

        self._click_combo = QComboBox()
        self._click_combo.setObjectName("DepthCombo")
        self._click_combo.setFixedHeight(30)
        for preset in CLICK_EFFECT_PRESETS:
            self._click_combo.addItem(preset.name)
        self._click_combo.setCurrentText(DEFAULT_CLICK_EFFECT.name)
        self._click_combo.currentTextChanged.connect(self._on_click_changed)
        click_lay.addWidget(self._click_combo)
        self._current_click_preset = DEFAULT_CLICK_EFFECT

        click_section = _CollapsibleSection("CLICK EFFECTS", click_body, collapsed=True)
        self._style_container.addWidget(click_section)

        # ── Output dimensions (collapsible) ──────────────────────────
        dim_body = QWidget()
        dim_lay = QVBoxLayout(dim_body)
        dim_lay.setContentsMargins(T.SPACE_LG, T.SPACE_MD, T.SPACE_LG, T.SPACE_SM)
        dim_lay.setSpacing(T.SPACE_SM)

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
        dim_lay.addWidget(self._dim_combo)

        self._current_output_dim = "auto"
        output_section = _CollapsibleSection("OUTPUT SIZE", dim_body, collapsed=True)
        self._style_container.addWidget(output_section)
        self._connect_exclusive_sections(
            [background_section, frame_section, click_section, output_section]
        )

        # Keep each task group pinned to the top of its own scroll region.
        self._motion_container.addStretch()
        self._style_container.addStretch()
        self._audio_container.addStretch()

        # ── Fixed bottom bar (outside scroll area) ──────────────────
        bottom_bar = QWidget()
        bottom_bar.setObjectName("InspectorBottomBar")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(T.SPACE_LG, T.SPACE_SM, T.SPACE_LG, T.SPACE_SM)
        bottom_layout.setSpacing(T.SPACE_XS)

        self._info_label = QLabel()
        info_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        self._info_label.setPixmap(info_icon.pixmap(16, 16))
        self._info_label.setObjectName("Secondary")
        self._info_label.setToolTip("Duration: 0:00\nMouse samples: 0\nKeyframes: 0")
        self._info_label.setCursor(Qt.CursorShape.WhatsThisCursor)
        bottom_layout.addWidget(self._info_label)
        bottom_layout.addStretch()

        self._btn_undo = QPushButton("Undo")
        self._btn_undo.setObjectName("CtrlBtn")
        self._btn_undo.setFixedHeight(28)
        self._btn_undo.setToolTip("Undo last zoom change (Ctrl+Z)")
        self._btn_undo.clicked.connect(self.undo_requested.emit)
        bottom_layout.addWidget(self._btn_undo)

        self._btn_redo = QPushButton("Redo")
        self._btn_redo.setObjectName("CtrlBtn")
        self._btn_redo.setFixedHeight(28)
        self._btn_redo.setToolTip("Redo last undone change (Ctrl+Y)")
        self._btn_redo.clicked.connect(self.redo_requested.emit)
        bottom_layout.addWidget(self._btn_redo)

        self._btn_settings = QPushButton("Settings")
        self._btn_settings.setObjectName("CtrlBtn")
        self._btn_settings.setFixedHeight(28)
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_settings.clicked.connect(self._show_settings_menu)
        bottom_layout.addWidget(self._btn_settings)
        outer.addWidget(bottom_bar)

        # Debug overlay state (managed via settings menu) — on by default
        self._debug_overlay_enabled = False

        # Encoder preference — deferred detection for faster startup.
        # Actual detection happens lazily on first settings menu open or export.
        self._encoder_id: str = "libx264"
        self._encoder_detected: bool = False

        self._mouse_track: List[MousePosition] = []
        self._key_events: List[KeyEvent] = []
        self._click_events: List[ClickEvent] = []
        self._monitor_rect: dict = {}

        # Fluent 2 — focus ring glow on all interactive controls
        for child in self.findChildren(QPushButton):
            install_focus_ring(child)
        for child in self.findChildren(QComboBox):
            install_focus_ring(child)

    @staticmethod
    def _connect_exclusive_sections(sections: list[_CollapsibleSection]) -> None:
        """Keep at most one disclosure body open within a task tab."""
        for section in sections:
            def collapse_siblings(current: _CollapsibleSection = section) -> None:
                for sibling in sections:
                    if sibling is not current:
                        sibling.set_collapsed(True)

            section.expanded.connect(collapse_siblings)

    # ── position / depth controls ───────────────────────────────────

    def _show_settings_menu(self) -> None:
        """Show settings popup menu from the cog button."""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {T.BG_INTERACTIVE}; color: {T.FG_PRIMARY};"
            f"  border: 1px solid {T.CARD_BORDER}; padding: {T.SPACE_XXS}px; }}"
            f"QMenu::item {{ padding: 6px 20px; }}"
            f"QMenu::item:selected {{ background: {T.BRAND}; }}"
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

        # AI settings
        menu.addSeparator()
        ai_act = menu.addAction("\U0001f916 AI Settings\u2026")
        ai_act.triggered.connect(self._show_ai_settings)

        # Encoder submenu
        encoder_menu = menu.addMenu("Video encoder")
        encoder_menu.setStyleSheet(menu.styleSheet())
        self._ensure_encoder_detected()
        available = _detect_encoders()
        for enc_id in available:
            label = _encoder_name(enc_id)
            tick = "✓ " if enc_id == self._encoder_id else "  "
            act = encoder_menu.addAction(f"{tick}{label}")
            act.setData(enc_id)
            act.triggered.connect(lambda checked=False, eid=enc_id: self._set_encoder(eid))

        # About
        menu.addSeparator()
        about_act = menu.addAction("About FollowCursor\u2026")
        about_act.triggered.connect(self._show_about)

        menu.exec(self._btn_settings.mapToGlobal(self._btn_settings.rect().topRight()))

    def _set_encoder(self, enc_id: str) -> None:
        """Update the selected encoder and emit signal."""
        self._encoder_id = enc_id
        self.encoder_changed.emit(enc_id)
        logger.info("Encoder set to: %s", _encoder_name(enc_id))

    @property
    def encoder_id(self) -> str:
        """The currently selected ffmpeg encoder ID."""
        self._ensure_encoder_detected()
        return self._encoder_id

    def _ensure_encoder_detected(self) -> None:
        """Lazily detect the best available encoder on first access."""
        if self._encoder_detected:
            return
        self._encoder_detected = True
        best = _best_encoder()
        if self._encoder_id == "libx264" and best != "libx264":
            self._encoder_id = best
            self.encoder_changed.emit(best)
            logger.info("Auto-detected encoder: %s", _encoder_name(best))

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
        grid.setSpacing(T.SPACE_XS)
        grid.setContentsMargins(0, T.SPACE_XS, 0, T.SPACE_XS)

        # Patterns get larger, fewer-per-row swatches so the pattern is visible
        if category == CAT_PATTERN:
            size, cols = 44, 4
        elif category == CAT_GRADIENT:
            size, cols = 36, 6
        else:
            size, cols = 28, 8

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
            border = T.BRAND_ACTIVE if is_active else "transparent"
            btn.setStyleSheet(self._bg_swatch_css(preset, border))

    @staticmethod
    def _bg_swatch_css(preset: BackgroundPreset, border: str) -> str:
        """Return QSS for a background swatch button."""
        r1, g1, b1 = preset.color_top
        r2, g2, b2 = preset.color_bottom
        kind = preset.kind
        hover = T.BRAND
        rad = T.RADIUS_SMALL

        if kind == "wavy":
            mr, mg, mb = (r1+r2)//2, (g1+g2)//2, (b1+b2)//2
            return (
                f"QPushButton {{ background: qlineargradient("
                f"x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:0.5 rgb({mr},{mg},{mb}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: {rad}px; }}"
                f"QPushButton:hover {{ border-color: {hover}; }}"
            )
        elif kind == "radial":
            return (
                f"QPushButton {{ background: qradialgradient("
                f"cx:0.5, cy:0.5, radius:0.7, fx:0.5, fy:0.5, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: {rad}px; }}"
                f"QPushButton:hover {{ border-color: {hover}; }}"
            )
        elif kind == "spotlight":
            return (
                f"QPushButton {{ background: qradialgradient("
                f"cx:0.8, cy:0.2, radius:0.9, fx:0.8, fy:0.2, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: {rad}px; }}"
                f"QPushButton:hover {{ border-color: {hover}; }}"
            )
        elif kind == "diagonal":
            return (
                f"QPushButton {{ background: qlineargradient("
                f"x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:0.25 rgb({r2},{g2},{b2}), "
                f"stop:0.5 rgb({r1},{g1},{b1}), "
                f"stop:0.75 rgb({r2},{g2},{b2}), "
                f"stop:1 rgb({r1},{g1},{b1})); "
                f"border: 2px solid {border}; border-radius: {rad}px; }}"
                f"QPushButton:hover {{ border-color: {hover}; }}"
            )
        elif kind == "dots":
            return (
                f"QPushButton {{ background: qradialgradient("
                f"cx:0.3, cy:0.3, radius:0.4, fx:0.3, fy:0.3, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: {rad}px; }}"
                f"QPushButton:hover {{ border-color: {hover}; }}"
            )
        elif kind == "chevron":
            mr, mg, mb = (r1+r2)//2, (g1+g2)//2, (b1+b2)//2
            return (
                f"QPushButton {{ background: qlineargradient("
                f"x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 rgb({r2},{g2},{b2}), "
                f"stop:0.3 rgb({r1},{g1},{b1}), "
                f"stop:0.5 rgb({r2},{g2},{b2}), "
                f"stop:0.7 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: {rad}px; }}"
                f"QPushButton:hover {{ border-color: {hover}; }}"
            )
        elif kind == "rings":
            return (
                f"QPushButton {{ background: qradialgradient("
                f"cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, "
                f"stop:0 rgb({r2},{g2},{b2}), "
                f"stop:0.4 rgb({r1},{g1},{b1}), "
                f"stop:0.6 rgb({r2},{g2},{b2}), "
                f"stop:0.8 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: {rad}px; }}"
                f"QPushButton:hover {{ border-color: {hover}; }}"
            )
        elif kind == "gradient":
            return (
                f"QPushButton {{ background: qlineargradient("
                f"x1:0, y1:0, x2:0, y2:1, "
                f"stop:0 rgb({r1},{g1},{b1}), "
                f"stop:1 rgb({r2},{g2},{b2})); "
                f"border: 2px solid {border}; border-radius: {rad}px; }}"
                f"QPushButton:hover {{ border-color: {hover}; }}"
            )
        else:  # solid
            return (
                f"QPushButton {{ background: rgb({r1},{g1},{b1}); "
                f"border: 2px solid {border}; border-radius: {rad}px; }}"
                f"QPushButton:hover {{ border-color: {hover}; }}"
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
        output_duration: float | None = None,
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

        out_dur = output_duration if output_duration is not None else duration
        tooltip = (
            f"Duration: {_fmt(duration)}\n"
            f"Output duration: {_fmt(out_dur)}\n"
            f"Mouse samples: {len(mouse_track):,}\n"
            f"Keyframes: {len(keyframes)}"
        )
        self._info_label.setToolTip(tooltip)

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
            self._auto_status.set_status("Not enough mouse data to analyze.")
            return
        if not self._monitor_rect:
            self._auto_status.set_status("No monitor info available.")
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
            self._auto_status.set_status(f"Analysis error: {exc}")
            return

        if not keyframes:
            self._auto_status.set_status("No significant activity clusters detected.")
            return

        # Count actual zoom-in keyframes (zoom > 1.0) as the cluster count
        n_clusters = sum(1 for kf in keyframes if kf.zoom > 1.0 and not kf.reason.startswith("Pan to:"))
        self._auto_status.set_status(
            f"Generated {len(keyframes)} keyframes from {n_clusters} activity cluster{'s' if n_clusters != 1 else ''}."
        )
        self.auto_keyframes_generated.emit(keyframes)

    # ── AI features ─────────────────────────────────────────────────

    def _on_ai_zoom(self) -> None:
        """Request AI-powered zoom analysis."""
        sens_name = self._sensitivity_combo.currentText()
        max_clusters, min_gap = SENSITIVITY_PRESETS.get(sens_name, (6, 4000))
        self._ai_zoom_status.set_status("Requesting AI analysis\u2026")
        self._btn_ai_zoom.setEnabled(False)
        self.ai_zoom_requested.emit(max_clusters, self._current_zoom_level, min_gap)

    def set_ai_zoom_status(self, text: str) -> None:
        """Update the AI zoom status label from outside."""
        self._ai_zoom_status.set_status(text)
        self._btn_ai_zoom.setEnabled(True)

    def _on_add_voiceover(self) -> None:
        """Request adding a voiceover segment at the current playback position."""
        self.add_voiceover_requested.emit(-1.0, "")  # voice selected in dialog

    def _on_generate_narration(self) -> None:
        """Request automated narration for the full recording."""
        guidance = self._narration_guidance.toPlainText().strip()
        self.generate_narration_requested.emit(self.selected_voice, guidance)

    def set_narration_status(self, text: str) -> None:
        """Update the narration status label from outside."""
        self._narration_status.set_status(text)
        if text:
            self._vo_status.set_status("")

    def set_voiceover_status(self, text: str) -> None:
        """Update the voiceover status label from outside."""
        self._vo_status.set_status(text)
        if text:
            self._narration_status.set_status("")
        self._btn_add_voiceover.setEnabled(True)

    def set_ai_busy(self, busy: bool) -> None:
        """Disable/enable AI buttons while an operation is in progress."""
        self._btn_ai_zoom.setEnabled(not busy)
        self._btn_generate_chapters.setEnabled(not busy)
        self._btn_generate_narration.setEnabled(not busy)
        self._btn_add_voiceover.setEnabled(not busy)

    @property
    def selected_voice(self) -> str:
        """Return the default TTS voice from settings."""
        from PySide6.QtCore import QSettings
        return QSettings("FollowCursor", "FollowCursor").value(
            "ai/ttsVoice", "en-US-Ava:DragonHDLatestNeural"
        )

    def _show_ai_settings(self) -> None:
        """Open the AI settings dialog."""
        from ..ai_service import AISettings
        from ..credentials import protect, unprotect
        from PySide6.QtCore import QSettings

        settings = QSettings("FollowCursor", "FollowCursor")
        current = AISettings(
            endpoint=settings.value("ai/endpoint", ""),
            api_key=unprotect(settings.value("ai/apiKey", "")),
            chat_model=settings.value("ai/chatModel", ""),
            narration_model=settings.value("ai/narrationModel", "gpt-5.4"),
            tts_voice=settings.value("ai/ttsVoice", "en-US-Ava:DragonHDLatestNeural"),
        )

        dlg = _AISettingsDialog(current, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.get_settings()
            settings.setValue("ai/endpoint", result.endpoint)
            settings.setValue("ai/apiKey", protect(result.api_key))
            settings.setValue("ai/chatModel", result.chat_model)
            settings.setValue("ai/narrationModel", result.narration_model)
            self.ai_settings_changed.emit()
            logger.info("AI settings updated")
            # Load available TTS voices in the background
            self._load_tts_voices(result.endpoint, result.api_key)

    def _load_tts_voices(self, endpoint: str, api_key: str) -> None:
        """Fetch en-US voices from Azure Speech Service on a background thread."""
        global _cached_voices
        if not endpoint or not api_key:
            return
        import threading

        def _fetch() -> None:
            global _cached_voices
            try:
                import azure.cognitiveservices.speech as speechsdk
                speech_config = speechsdk.SpeechConfig(
                    subscription=api_key,
                    endpoint=endpoint.rstrip("/"),
                )
                synthesizer = speechsdk.SpeechSynthesizer(
                    speech_config=speech_config, audio_config=None,
                )
                result = synthesizer.get_voices_async().get()
                if result.reason == speechsdk.ResultReason.VoicesListRetrieved:
                    _cached_voices = sorted(
                        v.short_name for v in result.voices
                        if v.locale == "en-US" and "Neural" in v.short_name
                    )
                    logger.info("Loaded %d en-US voices", len(_cached_voices))
            except Exception as exc:
                logger.warning("Failed to load TTS voices: %s", exc)

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_generate_chapters(self) -> None:
        """Request AI-generated chapter markers."""
        self.generate_chapters_requested.emit()

    def _on_add_chapter(self) -> None:
        """Add a chapter marker at the current playback position."""
        from ..models import Chapter
        chapter = Chapter(
            timestamp_ms=int(self._current_time_ms),
            name=f"Chapter",  # Will be auto-numbered by main_window
            auto_detected=False,
        )
        self.chapter_added.emit(chapter)

    def set_chapters_status(self, text: str) -> None:
        """Update the chapters status label from outside."""
        self._chapters_status.set_status(text)

    def _show_about(self) -> None:
        """Show the About dialog with links to GitHub."""
        from PySide6.QtWidgets import QMessageBox
        from ..version import __version__
        dlg = QMessageBox(self)
        dlg.setWindowTitle("About FollowCursor")
        dlg.setIcon(QMessageBox.Icon.NoIcon)
        dlg.setTextFormat(Qt.TextFormat.RichText)
        dlg.setText(
            f"<h3>FollowCursor v{__version__}</h3>"
            "<p>A Windows screen recorder with cinematic<br>"
            "cursor-following zoom and AI features.</p>"
            f'<p><a href="https://github.com/sabbour/followcursor" '
            f'style="color: {T.BRAND_ACTIVE};">GitHub Repository</a></p>'
            f'<p><a href="https://github.com/sabbour/followcursor/issues" '
            f'style="color: {T.BRAND_ACTIVE};">Report a Bug / Request a Feature</a></p>'
            f'<p style="color: {T.FG_MUTED}; font-size: {T.FONT_SIZE_CAPTION}px; margin-top: {T.SPACE_XS}px;">'
            "MIT License<br>"
            "Copyright \u00a9 2026 Ahmed Sabbour</p>"
        )
        dlg.setStyleSheet(
            f"QMessageBox {{ background: {T.BG_SURFACE}; }}"
            f"QMessageBox QLabel {{ color: {T.FG_PRIMARY}; font-size: {T.FONT_SIZE_BODY}px; }}"
            f"QPushButton {{ min-width: 80px; min-height: 28px;"
            f"  background: {T.BG_INTERACTIVE}; color: {T.FG_PRIMARY};"
            f"  border: 1px solid {T.CARD_BORDER};"
            f"  border-radius: {T.RADIUS_SMALL}px; padding: {T.SPACE_XXS}px {T.SPACE_MD}px; }}"
            f"QPushButton:hover {{ background: {T.BRAND}; }}"
        )
        dlg.exec()

    def _on_click_changed(self, name: str) -> None:
        """User picked a new click effect preset."""
        preset = next((p for p in CLICK_EFFECT_PRESETS if p.name == name), DEFAULT_CLICK_EFFECT)
        self._current_click_preset = preset
        self.click_effect_changed.emit(preset)

    def current_click_preset(self) -> ClickEffectPreset:
        """Return the currently selected click effect preset."""
        return self._current_click_preset

    def set_click_preset(self, preset: ClickEffectPreset) -> None:
        """Set the click effect preset from external code (e.g., project load)."""
        self._current_click_preset = preset
        self._click_combo.setCurrentText(preset.name)

