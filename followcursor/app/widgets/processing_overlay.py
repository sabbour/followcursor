"""Processing overlay — prominent banner shown while finishing a recording."""

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QLinearGradient
from PySide6.QtWidgets import QWidget


class ProcessingOverlay(QWidget):
    """Full-window translucent overlay with a pulsing 'Finishing recording…' banner."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setVisible(False)
        self._pulse: float = 0.0
        self._pulse_dir: float = 1.0
        self._title: str = "Finishing recording\u2026"
        self._subtitle: str = "Processing video, please wait"
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick)

    def show_overlay(
        self,
        title: str = "Finishing recording\u2026",
        subtitle: str = "Processing video, please wait",
    ) -> None:
        self._title = title
        self._subtitle = subtitle
        self._pulse = 0.0
        self._pulse_dir = 1.0
        self.setVisible(True)
        self.raise_()
        self.update()
        self._timer.start()

    def hide_overlay(self) -> None:
        self._timer.stop()
        self.setVisible(False)

    def _tick(self) -> None:
        self._pulse += self._pulse_dir * 0.04
        if self._pulse >= 1.0:
            self._pulse = 1.0
            self._pulse_dir = -1.0
        elif self._pulse <= 0.0:
            self._pulse = 0.0
            self._pulse_dir = 1.0
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Semi-transparent dark overlay
        painter.fillRect(self.rect(), QColor(19, 18, 33, 160))

        # Banner background — centered rounded rectangle with pulsing glow
        banner_w = min(420, w - 40)
        banner_h = 80
        bx = (w - banner_w) / 2
        by = (h - banner_h) / 2 - 20
        banner_rect = QRectF(bx, by, banner_w, banner_h)

        # Glow behind the banner (pulses)
        glow_alpha = int(40 + 30 * self._pulse)
        for r in range(20, 0, -4):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(139, 92, 246, glow_alpha))
            painter.drawRoundedRect(
                banner_rect.adjusted(-r, -r, r, r), 20 + r, 20 + r
            )

        # Banner fill
        grad = QLinearGradient(bx, by, bx + banner_w, by)
        grad.setColorAt(0, QColor(40, 38, 62))
        grad.setColorAt(1, QColor(55, 48, 85))
        painter.setBrush(grad)
        painter.setPen(QColor(139, 92, 246, 120))
        painter.drawRoundedRect(banner_rect, 16, 16)

        # Spinner dots
        import math
        cx = bx + 36
        cy = by + banner_h / 2
        for i in range(3):
            angle_offset = self._pulse * math.pi + i * (math.pi * 2 / 3)
            alpha = int(120 + 135 * abs(math.sin(angle_offset)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(139, 92, 246, alpha))
            dot_y = cy + math.sin(angle_offset) * 6
            painter.drawEllipse(QRectF(cx + i * 12 - 12, dot_y - 3, 6, 6))

        # Main text
        font = QFont()
        font.setFamily("Segoe UI Variable")
        font.setPixelSize(18)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(228, 228, 237))
        text_x = bx + 60
        text_y = by + banner_h / 2 - 4
        painter.drawText(int(text_x), int(text_y), self._title)

        # Sub text
        sub_font = QFont()
        sub_font.setFamily("Segoe UI Variable")
        sub_font.setPixelSize(12)
        painter.setFont(sub_font)
        painter.setPen(QColor(136, 134, 160))
        painter.drawText(int(text_x), int(text_y + 20), self._subtitle)
