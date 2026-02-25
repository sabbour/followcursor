"""Red border overlay window — frameless transparent window around the recorded monitor."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QGuiApplication
from PySide6.QtWidgets import QWidget


class RecordingBorderOverlay(QWidget):
    """Frameless, click-through, always-on-top window that draws a red border
    around the monitor being recorded."""

    BORDER_WIDTH = 4

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # Pulsing effect
        self._alpha: int = 255
        self._alpha_dir: int = -5
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(50)
        self._pulse_timer.timeout.connect(self._pulse)

    def show_on_monitor(self, monitor_index: int) -> None:
        """Position the border overlay around the given monitor and show it."""
        """Position and show around the given monitor using Qt screen geometry."""
        try:
            # Use Qt's screen list (index 1 in mss = screen 0 in Qt, etc.)
            screens = QGuiApplication.screens()
            qt_index = monitor_index - 1  # mss is 1-based, Qt is 0-based
            if qt_index < 0 or qt_index >= len(screens):
                qt_index = 0
            screen = screens[qt_index]
            geom = screen.geometry()

            # Draw the border INSIDE the monitor bounds so it isn't
            # clipped by adjacent monitors or desktop edges.
            self.setGeometry(
                geom.x(),
                geom.y(),
                geom.width(),
                geom.height(),
            )
            self.show()
            self._pulse_timer.start()
        except Exception:
            pass

    def hide_border(self) -> None:
        """Stop the pulse animation and hide the overlay."""
        self._pulse_timer.stop()
        self.hide()

    def _pulse(self) -> None:
        self._alpha += self._alpha_dir
        if self._alpha <= 140:
            self._alpha_dir = 5
        elif self._alpha >= 255:
            self._alpha_dir = -5
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bw = self.BORDER_WIDTH
        pen = QPen(QColor(239, 68, 68, self._alpha), bw)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Draw the border inset by half the pen width so it stays fully
        # inside the window (which now matches the monitor bounds exactly).
        half = bw / 2
        painter.drawRect(
            int(half), int(half),
            self.width() - bw, self.height() - bw,
        )
        painter.end()
