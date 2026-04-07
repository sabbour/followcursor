"""Source picker dialog — select a monitor or window to capture."""

from typing import Optional, List

from PySide6.QtCore import Qt, QThread, Signal as QtSignal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QGridLayout,
    QFrame,
    QTabWidget,
)
from PySide6.QtGui import QPixmap, QImage

from .. import tokens as T
from ..fluent_effects import apply_shadow

# ScreenRecorder imported lazily inside methods to avoid pulling in
# cv2/numpy/mss at startup.


# ── background workers ──────────────────────────────────────────


class _MonitorThumbWorker(QThread):
    """Grab monitor thumbnails off the main thread."""
    thumbnail_ready = QtSignal(int, object)  # monitor_index, QPixmap|None
    all_done = QtSignal()

    def __init__(self, monitors: list, parent=None):
        super().__init__(parent)
        self._monitors = monitors
        self._cancelled = False

    def cancel(self) -> None:
        """Request early termination."""
        self._cancelled = True

    def run(self):
        from ..screen_recorder import ScreenRecorder
        for mon in self._monitors:
            if self._cancelled:
                return
            thumb_qimg = ScreenRecorder.capture_thumbnail(mon["index"])
            pix = QPixmap.fromImage(thumb_qimg) if thumb_qimg else None
            self.thumbnail_ready.emit(mon["index"], pix)
        self.all_done.emit()


class _WindowThumbWorker(QThread):
    """Grab window thumbnails off the main thread."""
    thumbnail_ready = QtSignal(int, object)  # hwnd, QPixmap|None
    all_done = QtSignal()

    def __init__(self, windows: list, parent=None):
        super().__init__(parent)
        self._windows = windows
        self._cancelled = False

    def cancel(self) -> None:
        """Request early termination."""
        self._cancelled = True

    def run(self):
        import numpy as np
        from ..window_utils import capture_window_thumbnail

        for win in self._windows:
            if self._cancelled:
                return
            thumb = capture_window_thumbnail(win["hwnd"])
            if thumb is not None:
                h, w, c = thumb.shape
                qimg = QImage(thumb.data, w, h, w * c, QImage.Format.Format_RGB888)
                pix = QPixmap.fromImage(qimg.copy())
            else:
                pix = None
            self.thumbnail_ready.emit(win["hwnd"], pix)
        self.all_done.emit()


def _stop_thumb_worker(worker: QThread | None) -> None:
    """Safely stop and wait for a thumbnail worker thread."""
    if worker is None:
        return
    if hasattr(worker, "cancel"):
        worker.cancel()
    if worker.isRunning():
        worker.quit()
        worker.wait(3000)  # wait up to 3 s
    worker.deleteLater()


# ── source card ─────────────────────────────────────────────────


class _SourceCard(QFrame):
    """Clickable thumbnail card representing one capture source (monitor or window)."""
    def __init__(self, info: dict, thumb: Optional[QPixmap] = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source_info = info
        self._selected = False
        self.setObjectName("SourceCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(200, 155)
        self.setMaximumHeight(170)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._thumb_label = QLabel()
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setMinimumHeight(100)
        self._thumb_label.setStyleSheet(
            f"background: {T.BG_CANVAS}; border-radius: {T.RADIUS_SMALL}px;"
        )
        if thumb:
            self._thumb_label.setPixmap(
                thumb.scaled(self._thumb_label.width() or 400, 200,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            )
        layout.addWidget(self._thumb_label)

        display_name = info.get("name", info.get("title", "Unknown"))
        name_label = QLabel(display_name)
        name_label.setObjectName("Secondary")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        # Fluent 2 — subtle elevation shadow on cards
        apply_shadow(self, level="subtle")

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        self.setObjectName("SourceCardSelected" if value else "SourceCard")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.selected = True
        # deselect siblings
        parent = self.parentWidget()
        if parent:
            for child in parent.findChildren(_SourceCard):
                if child is not self:
                    child.selected = False


# ── dialog ──────────────────────────────────────────────────────


class SourcePickerDialog(QDialog):
    """Modal dialog that lists available monitors and windows."""

    def __init__(self, parent: QWidget | None = None,
                 exclude_hwnd: int = 0) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Source")
        self.setModal(True)
        self.setMinimumSize(760, 500)
        self.setObjectName("SourcePickerDialog")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

        self._exclude_hwnd = exclude_hwnd
        self._monitor_cards: List[_SourceCard] = []
        self._window_cards: List[_SourceCard] = []
        self._card_by_monitor: dict[int, _SourceCard] = {}
        self._card_by_hwnd: dict[int, _SourceCard] = {}
        self._mon_worker: _MonitorThumbWorker | None = None
        self._win_worker: _WindowThumbWorker | None = None
        self.chosen_source: dict = {}  # returned to caller

        # Fluent 2 — medium elevation shadow on floating dialogs
        apply_shadow(self, level="medium")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(8)

        title = QLabel("Select Source")
        title.setStyleSheet(
            f"font-size: {T.FONT_SIZE_HEADER}px; font-weight: 600;"
        )
        layout.addWidget(title)

        # Tabs: Screens | Windows
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; }}"
            f"QTabBar::tab {{ background: {T.BG_SURFACE}; color: {T.FG_SECONDARY};"
            f"  padding: {T.SPACE_XS}px 20px;"
            f"  border: none; border-bottom: 2px solid transparent;"
            f"  font-size: {T.FONT_SIZE_BODY}px; }}"
            f"QTabBar::tab:selected {{ color: {T.FG_PRIMARY};"
            f"  border-bottom: 2px solid {T.BRAND}; }}"
            f"QTabBar::tab:hover {{ color: {T.FG_PRIMARY}; }}"
        )
        self._tabs.addTab(self._build_screens_tab(), "\U0001f5a5  Screens")
        self._tabs.addTab(self._build_windows_tab(), "\U0001fa9f  Windows")
        layout.addWidget(self._tabs, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("CtrlBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        select_btn = QPushButton("Select")
        select_btn.setObjectName("SaveBtn")
        select_btn.clicked.connect(self._confirm)
        btn_row.addWidget(select_btn)
        layout.addLayout(btn_row)

    # ── tabs ────────────────────────────────────────────────────

    def _build_screens_tab(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        tab_layout = QVBoxLayout(widget)
        tab_layout.setContentsMargins(0, 8, 0, 0)

        subtitle = QLabel("Choose a monitor to record")
        subtitle.setObjectName("Secondary")
        tab_layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_widget)
        grid.setSpacing(16)

        from ..screen_recorder import ScreenRecorder
        monitors = ScreenRecorder.get_monitors()
        for i, mon in enumerate(monitors):
            mon["type"] = "monitor"
            card = _SourceCard(mon, None)
            if i == 0:
                card.selected = True
                self.chosen_source = mon
            card.mousePressEvent = self._make_card_click(card, card.mousePressEvent)
            self._monitor_cards.append(card)
            self._card_by_monitor[mon["index"]] = card
            grid.addWidget(card, i // 3, i % 3)

        scroll.setWidget(grid_widget)
        tab_layout.addWidget(scroll, 1)

        # Load thumbnails in background
        self._mon_worker = _MonitorThumbWorker(monitors, self)
        self._mon_worker.thumbnail_ready.connect(self._on_monitor_thumb)
        self._mon_worker.start()

        return widget

    def _build_windows_tab(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background: transparent;")
        tab_layout = QVBoxLayout(widget)
        tab_layout.setContentsMargins(0, 8, 0, 0)

        top_row = QHBoxLayout()
        subtitle = QLabel("Choose a window to record")
        subtitle.setObjectName("Secondary")
        top_row.addWidget(subtitle)
        top_row.addStretch()

        refresh_btn = QPushButton("\u21bb  Refresh")
        refresh_btn.setObjectName("CtrlBtn")
        refresh_btn.setFixedHeight(28)
        refresh_btn.clicked.connect(self._refresh_windows)
        top_row.addWidget(refresh_btn)
        tab_layout.addLayout(top_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._win_grid_widget = QWidget()
        self._win_grid_widget.setStyleSheet("background: transparent;")
        self._win_grid = QGridLayout(self._win_grid_widget)
        self._win_grid.setSpacing(16)

        scroll.setWidget(self._win_grid_widget)
        tab_layout.addWidget(scroll, 1)

        # Initial load
        self._refresh_windows()

        return widget

    # ── window list ─────────────────────────────────────────────

    def _refresh_windows(self) -> None:
        # Stop any previous thumbnail worker before starting a new one
        _stop_thumb_worker(self._win_worker)
        self._win_worker = None

        for card in self._window_cards:
            card.setParent(None)
            card.deleteLater()
        self._window_cards.clear()
        self._card_by_hwnd.clear()

        from ..window_utils import enumerate_windows
        windows = enumerate_windows(exclude_hwnd=self._exclude_hwnd)

        for i, win in enumerate(windows):
            card = _SourceCard(win, None)
            card.mousePressEvent = self._make_card_click(card, card.mousePressEvent)
            self._window_cards.append(card)
            self._card_by_hwnd[win["hwnd"]] = card
            self._win_grid.addWidget(card, i // 3, i % 3)

        if windows:
            self._win_worker = _WindowThumbWorker(windows, self)
            self._win_worker.thumbnail_ready.connect(self._on_window_thumb)
            self._win_worker.start()

    # ── thumbnail callbacks ─────────────────────────────────────

    def _on_monitor_thumb(self, monitor_index: int, pixmap) -> None:
        card = self._card_by_monitor.get(monitor_index)
        if card and pixmap:
            tw = card._thumb_label.width() or 400
            th = card._thumb_label.height() or 200
            card._thumb_label.setPixmap(
                pixmap.scaled(tw, th,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )

    def _on_window_thumb(self, hwnd: int, pixmap) -> None:
        card = self._card_by_hwnd.get(hwnd)
        if card and pixmap:
            tw = card._thumb_label.width() or 400
            th = card._thumb_label.height() or 200
            card._thumb_label.setPixmap(
                pixmap.scaled(tw, th,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )

    # ── card click handler ──────────────────────────────────────

    def _make_card_click(self, card: _SourceCard, original):
        def handler(event):
            original(event)
            self.chosen_source = card.source_info
            # Deselect all cards in the other group
            all_cards = self._monitor_cards + self._window_cards
            for c in all_cards:
                if c is not card:
                    c.selected = False
        return handler

    def _confirm(self) -> None:
        self.accept()

    def done(self, result: int) -> None:
        """Stop background thumbnail workers before closing the dialog."""
        _stop_thumb_worker(self._mon_worker)
        self._mon_worker = None
        _stop_thumb_worker(self._win_worker)
        self._win_worker = None
        super().done(result)
