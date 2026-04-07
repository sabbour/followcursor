"""Custom frameless title bar — Clipchamp-inspired."""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

from ..fluent_effects import install_focus_ring
from ..version import __version__
from ..icon_loader import load_icon
from .. import tokens as T


class TitleBar(QWidget):
    """Custom frameless title bar with logo, export button, and window controls.

    Supports drag-to-move, double-click-to-maximize, and displays the
    current project name with an unsaved-changes indicator.
    """

    export_clicked = Signal()
    discard_clicked = Signal()
    theme_toggle_clicked = Signal()  # New signal for theme toggle

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("TitleBar")
        self.setFixedHeight(46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(0)

        # ── left: logo ──────────────────────────────────────────
        self._logo_icon = QLabel()
        self._logo_icon.setPixmap(load_icon("play", variant="filled", color=T.BRAND).pixmap(16, 16))
        self._logo_icon.setStyleSheet("background: transparent; padding-right: 4px;")
        self._logo_icon.setFixedWidth(20)
        layout.addWidget(self._logo_icon)

        self._logo_text = QLabel("FollowCursor")
        self._logo_text.setObjectName("TitleBarLogo")
        layout.addWidget(self._logo_text)

        ver_label = QLabel(f"v{__version__}")
        ver_label.setStyleSheet(
            f"color: {T.FG_3}; font-size: {T.FONT_SIZE_CAPTION}px;"
            f" background: transparent; padding-left: {T.SPACE_6}px;"
        )
        layout.addWidget(ver_label)

        layout.addStretch()

        # ── right: theme toggle + export + window controls ─────────────
        self._btn_theme = QPushButton()
        self._btn_theme.setObjectName("ThemeToggleBtn")
        self._btn_theme.setFixedSize(32, 32)
        self._btn_theme.setToolTip("Toggle theme (Ctrl+T)")
        self._btn_theme.setIcon(load_icon("brightness_high", color=T.FG_2))
        self._btn_theme.setIconSize(QSize(20, 20))
        self._btn_theme.clicked.connect(self.theme_toggle_clicked.emit)
        install_focus_ring(self._btn_theme)
        layout.addWidget(self._btn_theme)

        layout.addSpacing(8)

        self._btn_export = QPushButton("  Export")
        self._btn_export.setIcon(load_icon("arrow_upload", color=T.FG_PRIMARY))
        self._btn_export.setObjectName("ExportBtn")
        self._btn_export.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self._btn_export)

        self._btn_discard = QPushButton("  Discard")
        self._btn_discard.setIcon(load_icon("delete", color=T.DANGER_TEXT))
        self._btn_discard.setObjectName("DiscardBtn")
        self._btn_discard.clicked.connect(self.discard_clicked.emit)
        self._btn_discard.setVisible(False)
        layout.addWidget(self._btn_discard)

        # Fluent 2 — keyboard focus glow on action buttons
        install_focus_ring(self._btn_export)
        install_focus_ring(self._btn_discard)

        layout.addSpacing(12)

        # window controls
        for text, name, slot in [
            ("─", "TitleBarBtn", self._minimize),
            ("□", "TitleBarBtn", self._maximize),
            ("✕", "TitleBarBtnClose", self._close),
        ]:
            btn = QPushButton(text)
            btn.setObjectName(name)
            btn.setFixedSize(40, 30)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

    # ── public ──────────────────────────────────────────────────────

    def refresh_icons(self, dark: bool = True) -> None:
        """Reload title-bar icons with colours for the active theme."""
        icon_fg = T.FG_2 if dark else T.LIGHT_FG_2
        self._btn_theme.setIcon(load_icon("brightness_high", color=icon_fg))

    def set_export_enabled(self, enabled: bool) -> None:
        """Enable or disable the export button."""
        self._btn_export.setEnabled(enabled)

    def set_export_text(self, text: str) -> None:
        """Update the export button label (e.g. during export progress)."""
        self._btn_export.setText(text)

    def set_discard_visible(self, visible: bool) -> None:
        """Show or hide the discard button."""
        self._btn_discard.setVisible(visible)

    def set_title(self, project_name: str = "", unsaved: bool = False) -> None:
        """Update the title bar text to show the current project name."""
        base = "FollowCursor"
        display = project_name if project_name else "Untitled project"
        dot = " ●" if unsaved else ""
        self._logo_text.setText(f"{base} — {display}{dot}")

    # ── window controls ─────────────────────────────────────────────

    def _minimize(self) -> None:
        self._window.showMinimized()

    def _maximize(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def _close(self) -> None:
        self._window.close()

    # ── drag to move (OS-native for Aero Snap support) ────────────

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle:
                handle.startSystemMove()

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        self._maximize()
