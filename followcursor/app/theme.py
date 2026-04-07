"""Dark theme QSS stylesheet — Fluent 2 / Windows 11 aligned design.

All colour values, spacing, and corner radii are sourced from the
centralised design-token module (:mod:`followcursor.app.tokens`).
Spacing is normalised to a 4 px base grid; radii use 4 px (controls)
and 8 px (containers).
"""

from . import tokens as T

DARK_THEME = f"""
/* ── Global ─────────────────────────────────────────── */
QWidget {{
    background-color: {T.BG_SURFACE};
    color: {T.FG_PRIMARY};
    font-family: {T.FONT_FAMILY};
    font-size: {T.FONT_SIZE_BODY}px;
    border: none;
}}
QWidget:focus {{ outline: none; }}

/* ── Title bar ──────────────────────────────────────── */
#TitleBar {{
    background-color: {T.BG_PANEL};
    border-bottom: 1px solid {T.BORDER_SUBTLE};
    min-height: 48px;
    max-height: 48px;
}}
#TitleBarLogo {{
    color: {T.FG_WHITE};
    font-size: {T.FONT_SIZE_BODY}px;
    font-weight: 600;
    background: transparent;
}}
#TitleBarBtn {{
    background: transparent;
    color: {T.FG_SECONDARY};
    border: none;
    border-radius: {T.RADIUS_SMALL}px;
    min-width: 40px; max-width: 40px;
    min-height: 32px; max-height: 32px;
    font-size: 14px;
}}
#TitleBarBtn:hover {{
    background-color: {T.BG_INTERACTIVE};
    color: {T.FG_PRIMARY};
}}
#TitleBarBtnClose {{
    background: transparent;
    color: {T.FG_SECONDARY};
    border: none;
    border-radius: {T.RADIUS_SMALL}px;
    min-width: 40px; max-width: 40px;
    min-height: 32px; max-height: 32px;
    font-size: 14px;
}}
#TitleBarBtnClose:hover {{
    background-color: {T.CLOSE_HOVER_BG};
    color: white;
}}
#ExportBtn {{
    height: 32px;
    padding: 0 {T.SPACE_LG}px;
    border-radius: {T.RADIUS_SMALL}px;
    background-color: {T.BRAND};
    border: none;
    color: white;
    font-size: {T.FONT_SIZE_BODY}px;
    font-weight: 600;
}}
#ExportBtn:hover {{
    background-color: {T.BRAND_HOVER};
}}
#ExportBtn:disabled {{
    background-color: {T.BRAND_DISABLED};
    color: {T.FG_DISABLED};
}}
#DiscardBtn {{
    height: 32px;
    padding: 0 {T.SPACE_LG}px;
    border-radius: {T.RADIUS_SMALL}px;
    background-color: {T.DISCARD_BG};
    border: none;
    color: {T.DANGER_TEXT};
    font-size: {T.FONT_SIZE_BODY}px;
    font-weight: 600;
}}
#DiscardBtn:hover {{
    background-color: {T.DISCARD_HOVER_BG};
    color: {T.DANGER_HOVER};
}}
#DiscardBtn:disabled {{
    background-color: {T.BG_ELEVATED};
    color: {T.FG_DISABLED};
}}

/* ── Sidebar ────────────────────────────────────────── */
#Sidebar {{
    background-color: {T.BG_PANEL};
    border-right: 1px solid {T.BORDER_SUBTLE};
}}
#SidebarBtn {{
    background: transparent;
    color: {T.FG_SECONDARY};
    border: none;
    border-radius: {T.RADIUS_MEDIUM}px;
    min-height: 56px; max-height: 56px;
    min-width: 56px; max-width: 56px;
    font-size: {T.FONT_SIZE_CAPTION}px;
    padding-top: {T.SPACE_XXS}px;
}}
#SidebarBtn:hover {{
    background-color: {T.BG_INTERACTIVE};
    color: {T.FG_PRIMARY};
}}
#SidebarBtnActive {{
    background-color: {T.BRAND_TRANSLUCENT};
    color: {T.BRAND_ACTIVE};
    border: none;
    border-radius: {T.RADIUS_MEDIUM}px;
    min-height: 56px; max-height: 56px;
    min-width: 56px; max-width: 56px;
    font-size: {T.FONT_SIZE_CAPTION}px;
    padding-top: {T.SPACE_XXS}px;
}}
#SidebarBtnActive:hover {{
    background-color: {T.BRAND_TRANSLUCENT_HOVER};
}}

/* ── Control bar buttons ────────────────────────────── */
#ControlBar {{
    background-color: {T.BG_CANVAS};
    min-height: 44px;
    max-height: 44px;
}}
QPushButton#CtrlBtn {{
    height: 34px;
    padding: 0 {T.SPACE_MD}px;
    border-radius: {T.RADIUS_SMALL}px;
    border: 1px solid {T.BORDER_MEDIUM};
    background-color: {T.BG_INTERACTIVE};
    color: {T.FG_PRIMARY};
    font-size: {T.FONT_SIZE_BODY}px;
    font-weight: 500;
}}
QPushButton#CtrlBtn:hover {{
    background-color: {T.BG_HOVER};
    border-color: {T.BORDER_STRONG};
}}
QPushButton#CtrlBtn:disabled {{
    background-color: {T.BG_ELEVATED};
    border-color: {T.BORDER_SUBTLE};
    color: {T.FG_DISABLED};
}}
QPushButton#RecordBtn {{
    height: 48px;
    padding: 0 40px;
    border-radius: {T.RADIUS_MEDIUM}px;
    background-color: {T.DANGER_DARK};
    border: 2px solid {T.DANGER_HOVER};
    color: white;
    font-size: {T.FONT_SIZE_TITLE}px;
    font-weight: 700;
    min-width: 220px;
    letter-spacing: 1px;
}}
QPushButton#RecordBtn:hover {{
    background-color: {T.DANGER};
    border-color: {T.DANGER_LIGHT};
}}
QPushButton#StopBtn {{
    height: 40px;
    padding: 0 {T.SPACE_LG}px;
    border-radius: {T.RADIUS_MEDIUM}px;
    background-color: {T.BG_INTERACTIVE};
    border: 2px solid {T.DANGER};
    color: {T.DANGER_HOVER};
    font-size: {T.FONT_SIZE_BODY}px;
    font-weight: 600;
    min-width: 160px;
}}
QPushButton#StopBtn:hover {{
    background-color: {T.DANGER_TRANSLUCENT};
}}
QPushButton#SaveBtn {{
    height: 40px;
    padding: 0 {T.SPACE_LG}px;
    border-radius: {T.RADIUS_MEDIUM}px;
    background-color: {T.BRAND};
    border: none;
    color: white;
    font-size: {T.FONT_SIZE_BODY}px;
    font-weight: 600;
}}
QPushButton#SaveBtn:hover {{
    background-color: {T.BRAND_HOVER};
}}
QPushButton#SaveBtn:disabled {{
    background-color: {T.BRAND_DISABLED};
    color: {T.FG_DISABLED};
}}

/* ── Preview area ───────────────────────────────────── */
#PreviewArea {{
    background-color: {T.BG_CANVAS};
}}
#PreviewWidget {{
    background: transparent;
}}
#PlaceholderWidget {{
    background-color: {T.BG_ELEVATED};
    border: 2px dashed {T.BORDER_MEDIUM};
    border-radius: {T.RADIUS_MEDIUM}px;
}}

/* ── Recording indicator ────────────────────────────── */
#RecIndicator {{
    background-color: {T.OVERLAY_BG};
    border: 1px solid {T.BORDER_SUBTLE};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_XXS}px {T.SPACE_MD}px;
}}
#RecDot {{
    background-color: {T.DANGER};
    min-width: 8px; max-width: 8px;
    min-height: 8px; max-height: 8px;
    border-radius: 4px;
}}
#RecTime {{
    color: {T.FG_PRIMARY};
    font-size: {T.FONT_SIZE_BODY}px;
    font-weight: 600;
    background: transparent;
}}

/* ── Editor panel ───────────────────────────────────── */
#EditorPanel {{
    background-color: {T.BG_PANEL};
    border-left: 1px solid {T.BORDER_SUBTLE};
    min-width: 280px;
    max-width: 280px;
}}
#EditorTitle {{
    color: {T.FG_SECONDARY};
    font-size: {T.FONT_SIZE_CAPTION}px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    background: transparent;
}}
#KfItem {{
    background-color: {T.BG_ELEVATED};
    border: 1px solid {T.BORDER_SUBTLE};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_XS}px {T.SPACE_SM}px;
}}
#KfItem:hover {{
    border-color: {T.BRAND};
    background-color: {T.BG_INTERACTIVE};
}}
#KfDeleteBtn {{
    background: transparent;
    color: {T.FG_SECONDARY};
    border: none;
    border-radius: {T.RADIUS_SMALL}px;
    min-width: 24px; max-width: 24px;
    min-height: 24px; max-height: 24px;
}}
#KfDeleteBtn:hover {{
    background-color: {T.DANGER_TRANSLUCENT_STRONG};
    color: {T.DANGER_HOVER};
}}

/* ── Timeline ───────────────────────────────────────── */
#TimelineArea {{
    background-color: {T.BG_PANEL};
    border-top: 1px solid {T.BORDER_SUBTLE};
}}
#PlaybackControls {{
    background: transparent;
}}
#PlayBtn {{
    background-color: {T.BG_INTERACTIVE};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.BORDER_MEDIUM};
    border-radius: {T.RADIUS_MEDIUM}px;
    min-width: 44px; max-width: 44px;
    min-height: 44px; max-height: 44px;
    font-size: {T.FONT_SIZE_HEADER}px;
}}
#PlayBtn:hover {{
    background-color: {T.BG_HOVER};
    border-color: {T.BORDER_STRONG};
}}
#PlayBtn:disabled {{
    background-color: {T.BG_ELEVATED};
    border-color: {T.BORDER_SUBTLE};
    color: {T.FG_DISABLED};
}}
#SkipBtn {{
    background: transparent;
    color: {T.FG_SECONDARY};
    border: none;
    border-radius: {T.RADIUS_SMALL}px;
    min-width: 36px; max-width: 36px;
    min-height: 36px; max-height: 36px;
    font-size: {T.FONT_SIZE_TITLE}px;
}}
#SkipBtn:hover {{
    background-color: {T.BG_INTERACTIVE};
    color: {T.FG_PRIMARY};
}}
#TimeDisplay {{
    color: {T.FG_PRIMARY};
    font-size: 12px;
    font-weight: 500;
    background: transparent;
    font-family: {T.FONT_FAMILY_MONO};
}}
#TimeDisplayDim {{
    color: {T.FG_DIM};
    font-size: 12px;
    font-weight: 500;
    background: transparent;
    font-family: {T.FONT_FAMILY_MONO};
}}

/* ── Status bar ─────────────────────────────────────── */
#StatusBar {{
    background-color: {T.BG_PANEL};
    border-top: 1px solid {T.BORDER_SUBTLE};
    min-height: 28px;
    max-height: 28px;
}}
#StatusLabel {{
    color: {T.FG_MUTED};
    font-size: {T.FONT_SIZE_CAPTION}px;
    background: transparent;
}}
#StatusDotReady {{
    background-color: {T.FG_MUTED};
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

/* ── Source picker dialog ───────────────────────────── */
#SourcePickerDialog {{
    background-color: {T.DIALOG_BG};
    border: 1px solid {T.BORDER_SUBTLE};
    border-radius: {T.RADIUS_MEDIUM}px;
}}
#SourceCard {{
    background-color: {T.CARD_BG};
    border: 2px solid {T.CARD_BORDER};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_XS}px;
}}
#SourceCard:hover {{
    border-color: {T.BRAND_ACTIVE};
    background-color: {T.CARD_HOVER_BG};
}}
#SourceCardSelected {{
    background-color: {T.CARD_HOVER_BG};
    border: 2px solid {T.BRAND};
    border-radius: {T.RADIUS_MEDIUM}px;
    padding: {T.SPACE_XS}px;
}}

/* ── Scrollbar ──────────────────────────────────────── */
QScrollBar:vertical {{
    width: 6px;
    background: transparent;
}}
QScrollBar::handle:vertical {{
    background: {T.BORDER_MEDIUM};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {T.BORDER_STRONG};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* ── Tooltips ───────────────────────────────────────── */
QToolTip {{
    background-color: {T.BG_INTERACTIVE};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.BORDER_MEDIUM};
    border-radius: {T.RADIUS_SMALL}px;
    padding: {T.SPACE_XXS}px {T.SPACE_XS}px;
    font-size: 12px;
}}

/* ── Misc ───────────────────────────────────────────── */
QLabel {{ background: transparent; }}
QLabel#Muted {{ color: {T.FG_MUTED}; font-size: 12px; }}
QLabel#Secondary {{ color: {T.FG_SECONDARY}; font-size: 12px; }}

/* ── Toggle buttons (Follow cursor / Fixed) ─────────── */
#ToggleBtn {{
    background-color: {T.BG_INTERACTIVE};
    color: {T.FG_SECONDARY};
    border: 1px solid {T.BORDER_MEDIUM};
    border-radius: {T.RADIUS_SMALL}px;
    font-size: 12px;
    font-weight: 500;
    padding: 0 {T.SPACE_MD}px;
}}
#ToggleBtn:hover {{
    background-color: {T.BG_HOVER};
    color: {T.FG_PRIMARY};
}}
#ToggleBtnActive {{
    background-color: {T.BRAND_TRANSLUCENT};
    color: {T.BRAND_ACTIVE};
    border: 1px solid {T.BRAND};
    border-radius: {T.RADIUS_SMALL}px;
    font-size: 12px;
    font-weight: 600;
    padding: 0 {T.SPACE_MD}px;
}}
#ToggleBtnActive:hover {{
    background-color: {T.BRAND_TRANSLUCENT_STRONG};
}}

/* ── Depth combo ────────────────────────────────────── */
#DepthCombo {{
    background-color: {T.BG_INTERACTIVE};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.BORDER_MEDIUM};
    border-radius: {T.RADIUS_SMALL}px;
    padding: {T.SPACE_XXS}px {T.SPACE_XS}px;
    font-size: 12px;
}}
#DepthCombo:hover {{
    border-color: {T.BORDER_STRONG};
}}
#DepthCombo::drop-down {{
    border: none;
    width: 20px;
}}
#DepthCombo::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {T.FG_SECONDARY};
    margin-right: {T.SPACE_XS}px;
}}
#DepthCombo QAbstractItemView {{
    background-color: {T.BG_INTERACTIVE};
    color: {T.FG_PRIMARY};
    border: 1px solid {T.BORDER_MEDIUM};
    border-radius: {T.RADIUS_SMALL}px;
    selection-background-color: {T.BRAND};
    selection-color: white;
    padding: {T.SPACE_XXS}px;
}}
"""
