"""
Fluent 2 animated button with smooth hover and press transitions.

Provides a drop-in replacement for QPushButton with Fluent 2 micro-interactions:
- Animated hover overlay (white, 6% opacity, 150ms OutCubic fade)
- Press overlay (black, 5% opacity, instant)
- Uses QPropertyAnimation on a custom hover_opacity Q_PROPERTY
"""

import logging
from PySide6.QtCore import QPropertyAnimation, Property, QEasingCurve, Qt
from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QPainter, QColor
from . import tokens as T

logger = logging.getLogger(__name__)


class FluentButton(QPushButton):
    """
    QPushButton subclass with Fluent 2 animated hover/press feedback.

    Animates a semi-transparent overlay on hover (150ms ease) and displays
    a press overlay on mouse down. Designed to work with existing QSS styles
    without requiring stylesheet changes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hover_opacity: float = 0.0
        self._pressed: bool = False

        # Setup hover animation
        self._hover_anim = QPropertyAnimation(self, b"hover_opacity")
        self._hover_anim.setDuration(T.DURATION_FAST)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setProperty("fluentAnimated", True)

    def get_hover_opacity(self) -> float:
        """Get current hover opacity value (0.0 to 1.0)."""
        return self._hover_opacity

    def set_hover_opacity(self, value: float) -> None:
        """Set hover opacity and trigger repaint."""
        self._hover_opacity = value
        self.update()

    hover_opacity = Property(float, get_hover_opacity, set_hover_opacity)

    def enterEvent(self, event):
        """Animate hover overlay fade-in on mouse enter."""
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_opacity)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Animate hover overlay fade-out on mouse leave."""
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_opacity)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Show press overlay on mouse down."""
        self._pressed = True
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Hide press overlay on mouse up."""
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """
        Paint button with animated overlay.

        Renders the base button style via super().paintEvent(), then draws
        a rounded-rect overlay matching Fluent 2 interaction specs:
        - Hover: white at 6% opacity (animated via hover_opacity property)
        - Press: black at 5% opacity (instant, overrides hover)
        """
        super().paintEvent(event)

        if self._hover_opacity > 0 or self._pressed:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect()

            # Match border radius to QSS (T.RADIUS_SMALL = 4px for buttons)
            radius = T.RADIUS_SMALL

            if self._pressed:
                # Press overlay: black at 5% opacity
                painter.setBrush(QColor(0, 0, 0, int(0.05 * 255)))
            else:
                # Hover overlay: white at 6% opacity, scaled by animation
                alpha = int(0.06 * 255 * self._hover_opacity)
                painter.setBrush(QColor(255, 255, 255, alpha))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, radius, radius)
            painter.end()
