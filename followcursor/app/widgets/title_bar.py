"""Custom frameless title bar — Clipchamp-inspired."""

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

from ..version import __version__


class TitleBar(QWidget):
    """Custom frameless title bar with logo, export button, and window controls.

    Supports drag-to-move, double-click-to-maximize, and displays the
    current project name with an unsaved-changes indicator.
    """

    export_clicked = Signal()

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._drag_pos: QPoint | None = None
        self.setObjectName("TitleBar")
        self.setFixedHeight(46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(0)

        # ── left: logo ──────────────────────────────────────────
        logo_icon = QLabel("▶")
        logo_icon.setStyleSheet(
            "color: #8b5cf6; font-size: 16px; background: transparent; padding-right: 4px;"
        )
        logo_icon.setFixedWidth(20)
        layout.addWidget(logo_icon)

        self._logo_text = QLabel("FollowCursor")
        self._logo_text.setObjectName("TitleBarLogo")
        layout.addWidget(self._logo_text)

        ver_label = QLabel(f"v{__version__}")
        ver_label.setStyleSheet(
            "color: #6c6890; font-size: 11px; background: transparent; padding-left: 6px;"
        )
        layout.addWidget(ver_label)

        layout.addStretch()

        # ── right: export + window controls ─────────────────────
        self._btn_export = QPushButton("⬆  Export")
        self._btn_export.setObjectName("ExportBtn")
        self._btn_export.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self._btn_export)

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

    def set_export_enabled(self, enabled: bool) -> None:
        """Enable or disable the export button."""
        self._btn_export.setEnabled(enabled)

    def set_export_text(self, text: str) -> None:
        """Update the export button label (e.g. during export progress)."""
        self._btn_export.setText(text)

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

    # ── drag to move ─────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._window.move(self._window.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        self._maximize()
