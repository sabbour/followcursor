"""Dark theme QSS stylesheet — Clipchamp-inspired design."""

DARK_THEME = """
/* ── Global ─────────────────────────────────────────── */
QWidget {
    background-color: #1b1a2e;
    color: #e4e4ed;
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    font-size: 13px;
    border: none;
}
QWidget:focus { outline: none; }

/* ── Title bar ──────────────────────────────────────── */
#TitleBar {
    background-color: #131221;
    border-bottom: 1px solid #2d2b45;
    min-height: 46px;
    max-height: 46px;
}
#TitleBarLogo {
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}
#TitleBarBtn {
    background: transparent;
    color: #8886a0;
    border: none;
    border-radius: 6px;
    min-width: 40px; max-width: 40px;
    min-height: 30px; max-height: 30px;
    font-size: 14px;
}
#TitleBarBtn:hover {
    background-color: #28263e;
    color: #e4e4ed;
}
#TitleBarBtnClose {
    background: transparent;
    color: #8886a0;
    border: none;
    border-radius: 6px;
    min-width: 40px; max-width: 40px;
    min-height: 30px; max-height: 30px;
    font-size: 14px;
}
#TitleBarBtnClose:hover {
    background-color: #c42b1c;
    color: white;
}
#ExportBtn {
    height: 32px;
    padding: 0 20px;
    border-radius: 6px;
    background-color: #8b5cf6;
    border: none;
    color: white;
    font-size: 13px;
    font-weight: 600;
}
#ExportBtn:hover {
    background-color: #9d74f7;
}

/* ── Sidebar ────────────────────────────────────────── */
#Sidebar {
    background-color: #131221;
    border-right: 1px solid #2d2b45;
}
#SidebarBtn {
    background: transparent;
    color: #8886a0;
    border: none;
    border-radius: 8px;
    min-height: 56px; max-height: 56px;
    min-width: 56px; max-width: 56px;
    font-size: 11px;
    padding-top: 4px;
}
#SidebarBtn:hover {
    background-color: #28263e;
    color: #e4e4ed;
}
#SidebarBtnActive {
    background-color: rgba(139, 92, 246, 0.18);
    color: #a78bfa;
    border: none;
    border-radius: 8px;
    min-height: 56px; max-height: 56px;
    min-width: 56px; max-width: 56px;
    font-size: 11px;
    padding-top: 4px;
}
#SidebarBtnActive:hover {
    background-color: rgba(139, 92, 246, 0.25);
}

/* ── Control bar buttons ────────────────────────────── */
#ControlBar {
    background-color: #0e0d19;
    min-height: 44px;
    max-height: 44px;
}
QPushButton#CtrlBtn {
    height: 34px;
    padding: 0 18px;
    border-radius: 6px;
    border: 1px solid #3d3b55;
    background-color: #28263e;
    color: #e4e4ed;
    font-size: 13px;
    font-weight: 500;
}
QPushButton#CtrlBtn:hover {
    background-color: #353350;
    border-color: #4e4c68;
}
QPushButton#RecordBtn {
    height: 50px;
    padding: 0 40px;
    border-radius: 12px;
    background-color: #dc2626;
    border: 2px solid #f87171;
    color: white;
    font-size: 16px;
    font-weight: 700;
    min-width: 220px;
    letter-spacing: 1px;
}
QPushButton#RecordBtn:hover {
    background-color: #ef4444;
    border-color: #fca5a5;
}
QPushButton#StopBtn {
    height: 38px;
    padding: 0 28px;
    border-radius: 8px;
    background-color: #28263e;
    border: 2px solid #ef4444;
    color: #f87171;
    font-size: 13px;
    font-weight: 600;
    min-width: 160px;
}
QPushButton#StopBtn:hover {
    background-color: rgba(239, 68, 68, 0.12);
}
QPushButton#SaveBtn {
    height: 38px;
    padding: 0 24px;
    border-radius: 8px;
    background-color: #8b5cf6;
    border: none;
    color: white;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#SaveBtn:hover {
    background-color: #9d74f7;
}
QPushButton#SaveBtn:disabled {
    background-color: #4c3d7a;
    color: #9898b0;
}

/* ── Preview area ───────────────────────────────────── */
#PreviewArea {
    background-color: #0e0d19;
}
#PreviewWidget {
    background: transparent;
}
#PlaceholderWidget {
    background-color: #201f34;
    border: 2px dashed #3d3b55;
    border-radius: 12px;
}

/* ── Recording indicator ────────────────────────────── */
#RecIndicator {
    background-color: rgba(19, 18, 33, 0.92);
    border: 1px solid #2d2b45;
    border-radius: 18px;
    padding: 4px 16px;
}
#RecDot {
    background-color: #ef4444;
    min-width: 8px; max-width: 8px;
    min-height: 8px; max-height: 8px;
    border-radius: 4px;
}
#RecTime {
    color: #e4e4ed;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}

/* ── Editor panel ───────────────────────────────────── */
#EditorPanel {
    background-color: #131221;
    border-left: 1px solid #2d2b45;
    min-width: 280px;
    max-width: 280px;
}
#EditorTitle {
    color: #8886a0;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    background: transparent;
}
#KfItem {
    background-color: #201f34;
    border: 1px solid #2d2b45;
    border-radius: 8px;
    padding: 8px 12px;
}
#KfItem:hover {
    border-color: #8b5cf6;
    background-color: #28263e;
}
#KfDeleteBtn {
    background: transparent;
    color: #8886a0;
    border: none;
    border-radius: 4px;
    min-width: 24px; max-width: 24px;
    min-height: 24px; max-height: 24px;
}
#KfDeleteBtn:hover {
    background-color: rgba(239, 68, 68, 0.15);
    color: #f87171;
}

/* ── Timeline ───────────────────────────────────────── */
#TimelineArea {
    background-color: #131221;
    border-top: 1px solid #2d2b45;
}
#PlaybackControls {
    background: transparent;
}
#PlayBtn {
    background-color: #28263e;
    color: #e4e4ed;
    border: 1px solid #3d3b55;
    border-radius: 8px;
    min-width: 44px; max-width: 44px;
    min-height: 44px; max-height: 44px;
    font-size: 20px;
}
#PlayBtn:hover {
    background-color: #353350;
    border-color: #4e4c68;
}
#SkipBtn {
    background: transparent;
    color: #8886a0;
    border: none;
    border-radius: 6px;
    min-width: 36px; max-width: 36px;
    min-height: 36px; max-height: 36px;
    font-size: 16px;
}
#SkipBtn:hover {
    background-color: #28263e;
    color: #e4e4ed;
}
#TimeDisplay {
    color: #e4e4ed;
    font-size: 12px;
    font-weight: 500;
    background: transparent;
    font-family: "Segoe UI Variable", "Segoe UI", monospace;
}
#TimeDisplayDim {
    color: #5a5873;
    font-size: 12px;
    font-weight: 500;
    background: transparent;
    font-family: "Segoe UI Variable", "Segoe UI", monospace;
}

/* ── Status bar ─────────────────────────────────────── */
#StatusBar {
    background-color: #131221;
    border-top: 1px solid #2d2b45;
    min-height: 26px;
    max-height: 26px;
}
#StatusLabel {
    color: #5a5873;
    font-size: 11px;
    background: transparent;
}
#StatusDotReady {
    background-color: #5a5873;
    min-width: 6px; max-width: 6px;
    min-height: 6px; max-height: 6px;
    border-radius: 3px;
}
#StatusDotRecording {
    background-color: #22c55e;
    min-width: 6px; max-width: 6px;
    min-height: 6px; max-height: 6px;
    border-radius: 3px;
}

/* ── Source picker dialog ───────────────────────────── */
#SourcePickerDialog {
    background-color: #141325;
    border: 1px solid #2d2b45;
    border-radius: 12px;
}
#SourceCard {
    background-color: #1e1d33;
    border: 2px solid #3d3a58;
    border-radius: 10px;
    padding: 8px;
}
#SourceCard:hover {
    border-color: #a78bfa;
    background-color: #2a2845;
}
#SourceCardSelected {
    background-color: #2a2845;
    border: 2px solid #8b5cf6;
    border-radius: 10px;
    padding: 8px;
}

/* ── Scrollbar ──────────────────────────────────────── */
QScrollBar:vertical {
    width: 6px;
    background: transparent;
}
QScrollBar::handle:vertical {
    background: #3d3b55;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #4e4c68;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

/* ── Tooltips ───────────────────────────────────────── */
QToolTip {
    background-color: #28263e;
    color: #e4e4ed;
    border: 1px solid #3d3b55;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}

/* ── Misc ───────────────────────────────────────────── */
QLabel { background: transparent; }
QLabel#Muted { color: #5a5873; font-size: 12px; }
QLabel#Secondary { color: #8886a0; font-size: 12px; }

/* ── Toggle buttons (Follow cursor / Fixed) ─────────── */
#ToggleBtn {
    background-color: #28263e;
    color: #8886a0;
    border: 1px solid #3d3b55;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    padding: 0 14px;
}
#ToggleBtn:hover {
    background-color: #353350;
    color: #e4e4ed;
}
#ToggleBtnActive {
    background-color: rgba(139, 92, 246, 0.18);
    color: #a78bfa;
    border: 1px solid #8b5cf6;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    padding: 0 14px;
}
#ToggleBtnActive:hover {
    background-color: rgba(139, 92, 246, 0.28);
}

/* ── Depth combo ────────────────────────────────────── */
#DepthCombo {
    background-color: #28263e;
    color: #e4e4ed;
    border: 1px solid #3d3b55;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 12px;
}
#DepthCombo:hover {
    border-color: #4e4c68;
}
#DepthCombo::drop-down {
    border: none;
    width: 20px;
}
#DepthCombo::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8886a0;
    margin-right: 6px;
}
#DepthCombo QAbstractItemView {
    background-color: #28263e;
    color: #e4e4ed;
    border: 1px solid #3d3b55;
    border-radius: 4px;
    selection-background-color: #8b5cf6;
    selection-color: white;
    padding: 4px;
}
"""
