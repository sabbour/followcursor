"""Dark theme QSS stylesheet — Fluent 2 / Windows 11 component patterns.

All color values, spacing, and corner radii are sourced from the
centralized design-token module (:mod:`followcursor.app.tokens`).
Component styling follows Fluent 2 Web patterns for buttons, tabs,
cards, inputs, menus, dialogs, sliders, and progress indicators.

Reference: https://fluent2.microsoft.design/components/web/react/
"""

from . import tokens as T

DARK_THEME = f"""
/* ══════════════════════════════════════════════════════════════
   GLOBAL BASE
   ══════════════════════════════════════════════════════════════ */
QWidget {{
    background-color: {T.BG_SURFACE};
    color: {T.FG_PRIMARY};
    font-family: {T.FONT_FAMILY};
    font-size: {T.FONT_SIZE_BODY_1}px;
    font-weight: {T.FONT_WEIGHT_REGULAR};
    border: none;
}}

/* ══════════════════════════════════════════════════════════════
   BUTTONS — Fluent 2 Button Patterns
   https://fluent2.microsoft.design/components/web/react/core/button/usage
   ══════════════════════════════════════════════════════════════ */

/* Base button (Secondary appearance) */
QPushButton {{
    background-color: {T.BG_LAYER_3};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_SMALL}px;
    padding: {T.SPACE_6}px {T.SPACE_MD}px;
    font-size: {T.FONT_SIZE_BODY_1}px;
    font-weight: {T.FONT_WEIGHT_MEDIUM};
    min-height: 32px;
}}
QPushButton:hover {{
    background-color: {T.BG_LAYER_4};
    border-color: {T.STROKE_ACCESSIBLE};
}}
QPushButton:pressed {{
    background-color: {T.BG_LAYER_2};
}}
QPushButton:disabled {{
    background-color: {T.BG_LAYER_2};
    color: {T.FG_DISABLED};
    border-color: {T.STROKE_2};
}}
/* Focus ring — Fluent 2 spec: 2px brand outline, 2px offset
   NOTE: Qt QSS doesn't support outline/outline-offset reliably.
   Using border instead, with padding adjustment to prevent size shift. */
QPushButton:focus {{
    border: 2px solid {T.BRAND};
    padding: {T.SPACE_XS - 1}px {T.SPACE_SM - 1}px;
}}

/* ══════════════════════════════════════════════════════════════
   INPUTS — Fluent 2 Input & Textarea Patterns
   https://fluent2.microsoft.design/components/web/react/core/input/usage
   ══════════════════════════════════════════════════════════════ */
QLineEdit, QTextEdit {{
    background-color: {T.BG_LAYER_2};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_SMALL}px;
    padding: {T.SPACE_6}px {T.SPACE_SM}px;
    font-size: {T.FONT_SIZE_BODY_1}px;
    selection-background-color: {T.BRAND};
    selection-color: {T.FG_PRIMARY};
}}
QLineEdit:hover, QTextEdit:hover {{
    border-color: {T.STROKE_ACCESSIBLE};
}}
QLineEdit:focus, QTextEdit:focus {{
    outline: {T.FOCUS_RING_WIDTH}px solid {T.BRAND};
    outline-offset: {T.FOCUS_RING_OFFSET}px;
    border-color: {T.BRAND};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    background-color: {T.BG_LAYER_1};
    color: {T.FG_DISABLED};
    border-color: {T.STROKE_2};
}}

/* ══════════════════════════════════════════════════════════════
   COMBOBOX / DROPDOWNS — Fluent 2 Dropdown Pattern
   https://fluent2.microsoft.design/components/web/react/core/dropdown/usage
   ══════════════════════════════════════════════════════════════ */
QComboBox {{
    background-color: {T.BG_LAYER_2};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_SMALL}px;
    padding: {T.SPACE_6}px {T.SPACE_SM}px;
    font-size: {T.FONT_SIZE_BODY_1}px;
    min-height: 32px;
}}
QComboBox:hover {{
    border-color: {T.STROKE_ACCESSIBLE};
}}
QComboBox:focus {{
    outline: {T.FOCUS_RING_WIDTH}px solid {T.BRAND};
    outline-offset: {T.FOCUS_RING_OFFSET}px;
    border-color: {T.BRAND};
}}
QComboBox:disabled {{
    background-color: {T.BG_LAYER_1};
    color: {T.FG_DISABLED};
    border-color: {T.STROKE_2};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {T.FG_2};
    margin-right: {T.SPACE_XS}px;
}}
QComboBox QAbstractItemView {{
    background-color: {T.BG_LAYER_4};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_XS}px;
    selection-background-color: {T.BG_SUBTLE_SELECTED};
    selection-color: {T.FG_PRIMARY};
}}
QComboBox QAbstractItemView::item {{
    padding: {T.SPACE_6}px {T.SPACE_SM}px;
    border-radius: {T.RADIUS_SMALL}px;
    min-height: 32px;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {T.BG_SUBTLE_HOVER};
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {T.BG_SUBTLE_SELECTED};
}}

/* ══════════════════════════════════════════════════════════════
   SPINBOX — Fluent 2 SpinButton Pattern
   https://fluent2.microsoft.design/components/web/react/core/spin/usage
   ══════════════════════════════════════════════════════════════ */
QSpinBox, QDoubleSpinBox {{
    background-color: {T.BG_LAYER_2};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_SMALL}px;
    padding: {T.SPACE_6}px {T.SPACE_SM}px;
    font-size: {T.FONT_SIZE_BODY_1}px;
    min-height: 32px;
}}
QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {T.STROKE_ACCESSIBLE};
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    outline: {T.FOCUS_RING_WIDTH}px solid {T.BRAND};
    outline-offset: {T.FOCUS_RING_OFFSET}px;
    border-color: {T.BRAND};
}}
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {T.BG_LAYER_1};
    color: {T.FG_DISABLED};
    border-color: {T.STROKE_2};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: transparent;
    border: none;
    border-radius: {T.RADIUS_SMALL}px;
    width: 24px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {T.BG_SUBTLE_HOVER};
}}

/* ══════════════════════════════════════════════════════════════
   CHECKBOX — Fluent 2 Checkbox Pattern
   https://fluent2.microsoft.design/components/web/react/core/checkbox/usage
   ══════════════════════════════════════════════════════════════ */
QCheckBox {{
    spacing: {T.SPACE_SM}px;
    color: {T.FG_PRIMARY};
    font-size: {T.FONT_SIZE_BODY_1}px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_SMALL}px;
    background-color: {T.BG_LAYER_2};
}}
QCheckBox::indicator:hover {{
    border-color: {T.STROKE_ACCESSIBLE};
    background-color: {T.BG_LAYER_3};
}}
QCheckBox::indicator:checked {{
    background-color: {T.BRAND};
    border-color: {T.BRAND};
}}
QCheckBox::indicator:checked:hover {{
    background-color: {T.BRAND_HOVER};
}}
QCheckBox::indicator:disabled {{
    background-color: {T.BG_LAYER_1};
    border-color: {T.STROKE_2};
}}
QCheckBox::indicator:focus {{
    border: 2px solid {T.BRAND};
}}
QCheckBox::indicator:checked:focus {{
    border: 2px solid {T.BRAND};
    background-color: {T.BRAND};
}}

/* ══════════════════════════════════════════════════════════════
   SLIDER — Fluent 2 Slider Pattern
   https://fluent2.microsoft.design/components/web/react/core/slider/usage
   ══════════════════════════════════════════════════════════════ */
QSlider {{
    min-height: 32px;
}}
QSlider::groove:horizontal {{
    background: {T.STROKE_1};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {T.BG_LAYER_5};
    border: 2px solid {T.BRAND};
    width: 16px;
    height: 16px;
    margin: -8px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: {T.BRAND_HOVER};
    border-color: {T.BRAND_HOVER};
}}
QSlider::handle:horizontal:pressed {{
    background: {T.BRAND_ACTIVE};
    border-color: {T.BRAND_ACTIVE};
}}
QSlider::sub-page:horizontal {{
    background: {T.BRAND};
    border-radius: 2px;
}}
QSlider:focus {{
    outline: {T.FOCUS_RING_WIDTH}px solid {T.BRAND};
    outline-offset: {T.FOCUS_RING_OFFSET}px;
}}
QSlider:disabled {{
    opacity: 0.4;
}}

/* ══════════════════════════════════════════════════════════════
   TABS — Fluent 2 TabList Pattern
   https://fluent2.microsoft.design/components/web/react/core/tablist/usage
   ══════════════════════════════════════════════════════════════ */
QTabWidget::pane {{
    border: none;
    background-color: {T.BG_LAYER_1};
}}
QTabBar {{
    background-color: transparent;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {T.FG_2};
    border: none;
    border-bottom: 2px solid transparent;
    padding: {T.SPACE_SM}px {T.SPACE_LG}px;
    font-size: {T.FONT_SIZE_BODY_1}px;
    font-weight: {T.FONT_WEIGHT_MEDIUM};
    min-height: 40px;
}}
QTabBar::tab:hover {{
    color: {T.FG_PRIMARY};
    background-color: {T.BG_SUBTLE_HOVER};
}}
QTabBar::tab:selected {{
    color: {T.FG_PRIMARY};
    border-bottom-color: {T.BRAND};
    font-weight: {T.FONT_WEIGHT_SEMIBOLD};
}}
QTabBar::tab:focus {{
    outline: {T.FOCUS_RING_WIDTH}px solid {T.BRAND};
    outline-offset: {T.FOCUS_RING_OFFSET}px;
}}

/* ══════════════════════════════════════════════════════════════
   CARDS — Fluent 2 Card Pattern
   https://fluent2.microsoft.design/components/web/react/core/card/usage
   ══════════════════════════════════════════════════════════════ */
QFrame#SourceCard, QFrame#PreviewCard {{
    background-color: {T.BG_CARD};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_SM}px;
}}
QFrame#SourceCard:hover, QFrame#PreviewCard:hover {{
    background-color: {T.BG_CARD_HOVER};
    border-color: {T.STROKE_ACCESSIBLE};
}}
QFrame#SourceCardSelected {{
    background-color: {T.BG_CARD_SELECTED};
    border: 2px solid {T.BRAND};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_SM}px;
}}

/* ══════════════════════════════════════════════════════════════
   MENU — Fluent 2 Menu Pattern
   https://fluent2.microsoft.design/components/web/react/core/menu/usage
   ══════════════════════════════════════════════════════════════ */
QMenu {{
    background-color: {T.BG_LAYER_4};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_XS}px;
}}
QMenu::item {{
    background-color: transparent;
    color: {T.FG_PRIMARY};
    padding: {T.SPACE_6}px {T.SPACE_MD}px {T.SPACE_6}px {T.SPACE_SM}px;
    border-radius: {T.RADIUS_SMALL}px;
    font-size: {T.FONT_SIZE_BODY_1}px;
    min-height: 32px;
}}
QMenu::item:selected {{
    background-color: {T.BG_SUBTLE_HOVER};
}}
QMenu::item:disabled {{
    color: {T.FG_DISABLED};
}}
QMenu::separator {{
    background-color: {T.STROKE_2};
    height: 1px;
    margin: {T.SPACE_XS}px 0;
}}
QMenu::icon {{
    padding-left: {T.SPACE_SM}px;
}}

/* ══════════════════════════════════════════════════════════════
   DIALOG — Fluent 2 Dialog Pattern
   https://fluent2.microsoft.design/components/web/react/core/dialog/usage
   ══════════════════════════════════════════════════════════════ */
QDialog {{
    background-color: {T.BG_LAYER_3};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_LARGE}px;
}}

/* ══════════════════════════════════════════════════════════════
   PROGRESS BAR — Fluent 2 ProgressBar Pattern
   https://fluent2.microsoft.design/components/web/react/core/progressbar/usage
   ══════════════════════════════════════════════════════════════ */
QProgressBar {{
    background-color: {T.BG_LAYER_2};
    border: none;
    border-radius: 2px;
    height: 4px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {T.BRAND};
    border-radius: 2px;
}}

/* ══════════════════════════════════════════════════════════════
   SCROLLBAR — Fluent 2 inspired minimal scrollbars
   ══════════════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    width: {T.SCROLLBAR_THIN}px;
    background: transparent;
    margin: {T.SPACE_XS}px 0;
    border-radius: {T.RADIUS_SMALL}px;
}}
QScrollBar:vertical:hover {{
    width: {T.SCROLLBAR_WIDE}px;
}}
QScrollBar::handle:vertical {{
    background: {T.STROKE_1};
    border-radius: {T.RADIUS_SMALL}px;
    min-height: {T.SCROLLBAR_MIN_HEIGHT}px;
}}
QScrollBar::handle:vertical:hover {{
    background: {T.STROKE_ACCESSIBLE};
}}
QScrollBar::handle:vertical:pressed {{
    background: {T.FG_2};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    height: {T.SCROLLBAR_THIN}px;
    background: transparent;
    margin: 0 {T.SPACE_XS}px;
    border-radius: {T.RADIUS_SMALL}px;
}}
QScrollBar:horizontal:hover {{
    height: {T.SCROLLBAR_WIDE}px;
}}
QScrollBar::handle:horizontal {{
    background: {T.STROKE_1};
    border-radius: {T.RADIUS_SMALL}px;
    min-width: {T.SCROLLBAR_MIN_HEIGHT}px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {T.STROKE_ACCESSIBLE};
}}
QScrollBar::handle:horizontal:pressed {{
    background: {T.FG_2};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* ══════════════════════════════════════════════════════════════
   TOOLTIPS — Fluent 2 Tooltip Pattern
   https://fluent2.microsoft.design/components/web/react/core/tooltip/usage
   ══════════════════════════════════════════════════════════════ */
QToolTip {{
    background-color: {T.BG_LAYER_5};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_6}px {T.SPACE_SM}px;
    font-size: {T.FONT_SIZE_CAPTION_1}px;
}}

/* ══════════════════════════════════════════════════════════════
   APP-SPECIFIC WIDGETS — FollowCursor Components
   ══════════════════════════════════════════════════════════════ */

/* ── Title Bar (Custom Frameless Window Title) ──── */
#TitleBar {{
    background-color: {T.BG_LAYER_1};
    border-bottom: 1px solid {T.STROKE_2};
    min-height: 48px;
    max-height: 48px;
}}
#TitleBarLogo {{
    color: {T.FG_PRIMARY};
    font-size: {T.FONT_SIZE_BODY_1}px;
    font-weight: {T.FONT_WEIGHT_SEMIBOLD};
    background: transparent;
}}
/* Subtle appearance title bar buttons */
#TitleBarBtn {{
    background: transparent;
    color: {T.FG_2};
    border: none;
    border-radius: {T.RADIUS_SMALL}px;
    min-width: 40px; max-width: 40px;
    min-height: 32px; max-height: 32px;
    font-size: {T.FONT_SIZE_BODY_1}px;
    padding: 0;
}}
#TitleBarBtn:hover {{
    background-color: {T.BG_SUBTLE_HOVER};
    color: {T.FG_PRIMARY};
}}
#TitleBarBtnClose {{
    background: transparent;
    color: {T.FG_2};
    border: none;
    border-radius: {T.RADIUS_SMALL}px;
    min-width: 40px; max-width: 40px;
    min-height: 32px; max-height: 32px;
    font-size: {T.FONT_SIZE_BODY_1}px;
    padding: 0;
}}
#TitleBarBtnClose:hover {{
    background-color: {T.CLOSE_HOVER_BG};
    color: white;
}}
/* Primary button — Export */
#ExportBtn {{
    height: 32px;
    padding: 0 {T.SPACE_LG}px;
    border-radius: {T.RADIUS_SMALL}px;
    background-color: {T.BRAND};
    border: none;
    color: white;
    font-size: {T.FONT_SIZE_BODY_1}px;
    font-weight: {T.FONT_WEIGHT_SEMIBOLD};
}}
#ExportBtn:hover {{
    background-color: {T.BRAND_HOVER};
}}
#ExportBtn:pressed {{
    background-color: {T.BRAND_ACTIVE};
}}
#ExportBtn:disabled {{
    background-color: {T.BRAND_DISABLED};
    color: {T.FG_DISABLED};
}}
/* Subtle button with danger color — Discard */
#DiscardBtn {{
    height: 32px;
    padding: 0 {T.SPACE_LG}px;
    border-radius: {T.RADIUS_SMALL}px;
    background-color: transparent;
    border: 1px solid {T.STROKE_1};
    color: {T.DANGER};
    font-size: {T.FONT_SIZE_BODY_1}px;
    font-weight: {T.FONT_WEIGHT_SEMIBOLD};
}}
#DiscardBtn:hover {{
    background-color: {T.DANGER_TRANSLUCENT};
    border-color: {T.DANGER};
    color: {T.DANGER_HOVER};
}}
#DiscardBtn:pressed {{
    background-color: {T.DANGER_TRANSLUCENT_STRONG};
}}
#DiscardBtn:disabled {{
    background-color: transparent;
    border-color: {T.STROKE_2};
    color: {T.FG_DISABLED};
}}

/* ── Sidebar ──── */
#Sidebar {{
    background-color: {T.BG_LAYER_1};
    border-right: 1px solid {T.STROKE_2};
}}
/* Vertical nav buttons — Transparent appearance */
#SidebarBtn {{
    background: transparent;
    color: {T.FG_2};
    border: none;
    border-radius: {T.RADIUS_MEDIUM}px;
    min-height: 64px; max-height: 64px;
    min-width: 64px; max-width: 64px;
    font-size: {T.FONT_SIZE_CAPTION_1}px;
    font-weight: {T.FONT_WEIGHT_REGULAR};
    padding-top: {T.SPACE_XS}px;
}}
#SidebarBtn:hover {{
    background-color: {T.BG_SUBTLE_HOVER};
    color: {T.FG_PRIMARY};
}}
#SidebarBtnActive {{
    background-color: {T.BRAND_TRANSLUCENT};
    color: {T.BRAND};
    border: none;
    border-radius: {T.RADIUS_MEDIUM}px;
    min-height: 64px; max-height: 64px;
    min-width: 64px; max-width: 64px;
    font-size: {T.FONT_SIZE_CAPTION_1}px;
    font-weight: {T.FONT_WEIGHT_SEMIBOLD};
    padding-top: {T.SPACE_XS}px;
}}
#SidebarBtnActive:hover {{
    background-color: {T.BRAND_TRANSLUCENT_HOVER};
}}

/* ── Control Bar Buttons ──── */
#ControlBar {{
    background-color: {T.BG_LAYER_1};
    min-height: 56px;
    max-height: 56px;
}}
/* Secondary appearance control buttons */
QPushButton#CtrlBtn {{
    height: 36px;
    padding: 0 {T.SPACE_LG}px;
    border-radius: {T.RADIUS_SMALL}px;
    border: 1px solid {T.STROKE_1};
    background-color: {T.BG_LAYER_3};
    color: {T.FG_PRIMARY};
    font-size: {T.FONT_SIZE_BODY_1}px;
    font-weight: {T.FONT_WEIGHT_MEDIUM};
}}
QPushButton#CtrlBtn:hover {{
    background-color: {T.BG_LAYER_4};
    border-color: {T.STROKE_ACCESSIBLE};
}}
QPushButton#CtrlBtn:pressed {{
    background-color: {T.BG_LAYER_2};
}}
QPushButton#CtrlBtn:disabled {{
    background-color: {T.BG_LAYER_2};
    border-color: {T.STROKE_2};
    color: {T.FG_DISABLED};
}}
/* Primary danger button — Record */
QPushButton#RecordBtn {{
    height: 48px;
    padding: 0 {T.SPACE_XXL}px;
    border-radius: {T.RADIUS_MEDIUM}px;
    background-color: {T.DANGER};
    border: none;
    color: white;
    font-size: {T.FONT_SIZE_SUBTITLE_2}px;
    font-weight: {T.FONT_WEIGHT_BOLD};
    min-width: 200px;
}}
QPushButton#RecordBtn:hover {{
    background-color: {T.DANGER_HOVER};
}}
QPushButton#RecordBtn:pressed {{
    background-color: {T.DANGER_DARK};
}}
/* Secondary button with danger outline — Stop */
QPushButton#StopBtn {{
    height: 40px;
    padding: 0 {T.SPACE_XL}px;
    border-radius: {T.RADIUS_MEDIUM}px;
    background-color: transparent;
    border: 2px solid {T.DANGER};
    color: {T.DANGER};
    font-size: {T.FONT_SIZE_BODY_1}px;
    font-weight: {T.FONT_WEIGHT_SEMIBOLD};
    min-width: 140px;
}}
QPushButton#StopBtn:hover {{
    background-color: {T.DANGER_TRANSLUCENT};
    color: {T.DANGER_HOVER};
}}
QPushButton#StopBtn:pressed {{
    background-color: {T.DANGER_TRANSLUCENT_STRONG};
}}
/* Primary brand button — Save */
QPushButton#SaveBtn {{
    height: 40px;
    padding: 0 {T.SPACE_XL}px;
    border-radius: {T.RADIUS_MEDIUM}px;
    background-color: {T.BRAND};
    border: none;
    color: white;
    font-size: {T.FONT_SIZE_BODY_1}px;
    font-weight: {T.FONT_WEIGHT_SEMIBOLD};
}}
QPushButton#SaveBtn:hover {{
    background-color: {T.BRAND_HOVER};
}}
QPushButton#SaveBtn:pressed {{
    background-color: {T.BRAND_ACTIVE};
}}
QPushButton#SaveBtn:disabled {{
    background-color: {T.BRAND_DISABLED};
    color: {T.FG_DISABLED};
}}

/* ── Preview Area ──── */
#PreviewArea {{
    background-color: {T.BG_LAYER_1};
}}
#PreviewWidget {{
    background: transparent;
}}
#PlaceholderWidget {{
    background-color: {T.BG_LAYER_2};
    border: 2px dashed {T.STROKE_1};
    border-radius: {T.RADIUS_MEDIUM}px;
}}

/* ── Recording Indicator ──── */
#RecIndicator {{
    background-color: {T.OVERLAY_BG};
    border: 1px solid {T.STROKE_2};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_6}px {T.SPACE_MD}px;
}}
#RecDot {{
    background-color: {T.DANGER};
    min-width: 8px; max-width: 8px;
    min-height: 8px; max-height: 8px;
    border-radius: 4px;
}}
#RecTime {{
    color: {T.FG_PRIMARY};
    font-size: {T.FONT_SIZE_BODY_1}px;
    font-weight: {T.FONT_WEIGHT_SEMIBOLD};
    background: transparent;
}}

/* ── Editor Panel ──── */
#EditorPanel {{
    background-color: {T.BG_LAYER_1};
    border-left: 1px solid {T.STROKE_2};
    min-width: 280px;
    max-width: 280px;
}}
#EditorTitle {{
    color: {T.FG_2};
    font-size: {T.FONT_SIZE_CAPTION_1}px;
    font-weight: {T.FONT_WEIGHT_SEMIBOLD};
    text-transform: uppercase;
    letter-spacing: 1px;
    background: transparent;
}}
/* Keyframe item card */
#KfItem {{
    background-color: {T.BG_LAYER_3};
    border: 1px solid {T.STROKE_2};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_SM}px;
}}
#KfItem:hover {{
    border-color: {T.BRAND};
    background-color: {T.BG_LAYER_4};
}}
/* Subtle delete button */
#KfDeleteBtn {{
    background: transparent;
    color: {T.FG_2};
    border: none;
    border-radius: {T.RADIUS_SMALL}px;
    min-width: 28px; max-width: 28px;
    min-height: 28px; max-height: 28px;
}}
#KfDeleteBtn:hover {{
    background-color: {T.DANGER_TRANSLUCENT};
    color: {T.DANGER_HOVER};
}}

/* ── Timeline ──── */
#TimelineArea {{
    background-color: {T.BG_LAYER_1};
    border-top: 1px solid {T.STROKE_2};
}}
#PlaybackControls {{
    background: transparent;
}}
/* Play button — secondary */
#PlayBtn {{
    background-color: {T.BG_LAYER_3};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_MEDIUM}px;
    min-width: 44px; max-width: 44px;
    min-height: 44px; max-height: 44px;
    font-size: {T.FONT_SIZE_SUBTITLE_2}px;
}}
#PlayBtn:hover {{
    background-color: {T.BG_LAYER_4};
    border-color: {T.STROKE_ACCESSIBLE};
}}
#PlayBtn:pressed {{
    background-color: {T.BG_LAYER_2};
}}
#PlayBtn:disabled {{
    background-color: {T.BG_LAYER_2};
    border-color: {T.STROKE_2};
    color: {T.FG_DISABLED};
}}
/* Transparent skip buttons */
#SkipBtn {{
    background: transparent;
    color: {T.FG_2};
    border: none;
    border-radius: {T.RADIUS_SMALL}px;
    min-width: 36px; max-width: 36px;
    min-height: 36px; max-height: 36px;
    font-size: {T.FONT_SIZE_SUBTITLE_2}px;
}}
#SkipBtn:hover {{
    background-color: {T.BG_SUBTLE_HOVER};
    color: {T.FG_PRIMARY};
}}
#TimeDisplay {{
    color: {T.FG_PRIMARY};
    font-size: {T.FONT_SIZE_CAPTION_1}px;
    font-weight: {T.FONT_WEIGHT_MEDIUM};
    background: transparent;
    font-family: {T.FONT_FAMILY_MONO};
}}
#TimeDisplayDim {{
    color: {T.FG_3};
    font-size: {T.FONT_SIZE_CAPTION_1}px;
    font-weight: {T.FONT_WEIGHT_MEDIUM};
    background: transparent;
    font-family: {T.FONT_FAMILY_MONO};
}}

/* ── Status Bar ──── */
#StatusBar {{
    background-color: {T.BG_LAYER_1};
    border-top: 1px solid {T.STROKE_2};
    min-height: 28px;
    max-height: 28px;
}}
#StatusLabel {{
    color: {T.FG_3};
    font-size: {T.FONT_SIZE_CAPTION_1}px;
    background: transparent;
}}
#StatusDotReady {{
    background-color: {T.FG_3};
    min-width: 6px; max-width: 6px;
    min-height: 6px; max-height: 6px;
    border-radius: 3px;
}}
#StatusDotRecording {{
    background-color: {T.SUCCESS};
    min-width: 6px; max-width: 6px;
    min-height: 6px; max-height: 6px;
    border-radius: 3px;
}}
#StatusDotWarning {{
    background-color: {T.WARNING};
    min-width: 6px; max-width: 6px;
    min-height: 6px; max-height: 6px;
    border-radius: 3px;
}}
#StatusDotInfo {{
    background-color: {T.INFO};
    min-width: 6px; max-width: 6px;
    min-height: 6px; max-height: 6px;
    border-radius: 3px;
}}

/* ── Source Picker Dialog ──── */
#SourcePickerDialog {{
    background-color: {T.BG_LAYER_3};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_LARGE}px;
}}
#SourcePickerDialog QTabWidget::pane {{
    background-color: transparent;
}}

/* ── Misc Labels ──── */
QLabel {{ background: transparent; }}
QLabel#Muted {{ color: {T.FG_3}; font-size: {T.FONT_SIZE_CAPTION_1}px; }}
QLabel#Secondary {{ color: {T.FG_2}; font-size: {T.FONT_SIZE_CAPTION_1}px; }}

/* ── Toggle Buttons (Fluent 2 Toggle Pattern) ──── */
#ToggleBtn {{
    background-color: {T.BG_LAYER_3};
    color: {T.FG_2};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_SMALL}px;
    font-size: {T.FONT_SIZE_CAPTION_1}px;
    font-weight: {T.FONT_WEIGHT_MEDIUM};
    padding: {T.SPACE_6}px {T.SPACE_MD}px;
    min-height: 32px;
}}
#ToggleBtn:hover {{
    background-color: {T.BG_LAYER_4};
    color: {T.FG_PRIMARY};
}}
#ToggleBtnActive {{
    background-color: {T.BRAND_TRANSLUCENT};
    color: {T.BRAND};
    border: 1px solid {T.BRAND};
    border-radius: {T.RADIUS_SMALL}px;
    font-size: {T.FONT_SIZE_CAPTION_1}px;
    font-weight: {T.FONT_WEIGHT_SEMIBOLD};
    padding: {T.SPACE_6}px {T.SPACE_MD}px;
    min-height: 32px;
}}
#ToggleBtnActive:hover {{
    background-color: {T.BRAND_TRANSLUCENT_STRONG};
}}

/* ── Depth Combo (legacy styled combobox) ──── */
#DepthCombo {{
    background-color: {T.BG_LAYER_3};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_SMALL}px;
    padding: {T.SPACE_6}px {T.SPACE_SM}px;
    font-size: {T.FONT_SIZE_CAPTION_1}px;
}}
#DepthCombo:hover {{
    border-color: {T.STROKE_ACCESSIBLE};
}}
#DepthCombo::drop-down {{
    border: none;
    width: 24px;
}}
#DepthCombo::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {T.FG_2};
    margin-right: {T.SPACE_SM}px;
}}
#DepthCombo QAbstractItemView {{
    background-color: {T.BG_LAYER_4};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.STROKE_1};
    border-radius: {T.RADIUS_MEDIUM}px;
    selection-background-color: {T.BRAND};
    selection-color: {T.FG_PRIMARY};
    padding: {T.SPACE_XS}px;
}}
"""
