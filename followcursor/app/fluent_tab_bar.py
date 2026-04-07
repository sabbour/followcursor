"""
Fluent 2 animated tab bar with smooth hover transitions.

Provides a drop-in replacement for QTabBar with Fluent 2 micro-interactions:
- Animated hover overlay (white, 6% opacity, 150ms OutCubic fade)
- Press overlay (black, 5% opacity, instant)
- Uses QPropertyAnimation on a custom hover_opacity Q_PROPERTY per tab
"""

import logging
from PySide6.QtCore import QPropertyAnimation, Property, QEasingCurve, Qt
from PySide6.QtWidgets import QTabBar
from PySide6.QtGui import QPainter, QColor, QMouseEvent
from . import tokens as T

logger = logging.getLogger(__name__)


class FluentTabBar(QTabBar):
    """
    QTabBar subclass with Fluent 2 animated hover/press feedback.

    Animates a semi-transparent overlay on hover (150ms ease) and displays
    a press overlay on mouse down. Tracks hover state per tab and renders
    overlays via paintEvent.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hover_tab: int = -1  # Index of currently hovered tab (-1 = none)
        self._hover_opacity: float = 0.0
        self._pressed_tab: int = -1  # Index of pressed tab (-1 = none)

        # Setup hover animation
        self._hover_anim = QPropertyAnimation(self, b"hover_opacity")
        self._hover_anim.setDuration(T.DURATION_FAST)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Enable mouse tracking to detect hover
        self.setMouseTracking(True)
        self.setProperty("fluentAnimated", True)

    def get_hover_opacity(self) -> float:
        """Get current hover opacity value (0.0 to 1.0)."""
        return self._hover_opacity

    def set_hover_opacity(self, value: float) -> None:
        """Set hover opacity and trigger repaint."""
        self._hover_opacity = value
        self.update()

    hover_opacity = Property(float, get_hover_opacity, set_hover_opacity)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Track which tab is currently hovered."""
        tab_index = self.tabAt(event.pos())
        if tab_index != self._hover_tab:
            # Hover state changed
            if tab_index == -1:
                # Mouse left all tabs
                self._start_fade_out()
            else:
                # Mouse entered a tab
                if self._hover_tab == -1:
                    # Was not hovering any tab, fade in
                    self._start_fade_in()
                # else: moving between tabs, keep current opacity
            self._hover_tab = tab_index
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Animate hover overlay fade-out on mouse leave."""
        self._hover_tab = -1
        self._start_fade_out()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Show press overlay on mouse down."""
        self._pressed_tab = self.tabAt(event.pos())
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Hide press overlay on mouse up."""
        self._pressed_tab = -1
        self.update()
        super().mouseReleaseEvent(event)

    def _start_fade_in(self):
        """Start hover fade-in animation."""
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_opacity)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()

    def _start_fade_out(self):
        """Start hover fade-out animation."""
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_opacity)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()

    def paintEvent(self, event):
        """
        Paint tab bar with animated overlay.

        Renders the base tab bar style via super().paintEvent(), then draws
        a rounded-rect overlay on the hovered/pressed tab matching Fluent 2
        interaction specs:
        - Hover: white at 6% opacity (animated via hover_opacity property)
        - Press: black at 5% opacity (instant, overrides hover)
        """
        super().paintEvent(event)

        # Only draw overlay if hovering or pressing a valid tab
        if (self._hover_opacity > 0 and self._hover_tab >= 0) or self._pressed_tab >= 0:
            # Determine which tab to overlay — validate before creating painter
            target_tab = self._pressed_tab if self._pressed_tab >= 0 else self._hover_tab
            if target_tab < 0 or target_tab >= self.count():
                return

            rect = self.tabRect(target_tab)
            if rect.isNull():
                return

            painter = QPainter(self)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                # QTabBar::tab has no border-radius in theme.py — use T.RADIUS_NONE
                radius = T.RADIUS_NONE

                if self._pressed_tab >= 0:
                    # Press overlay: black at 5% opacity
                    painter.setBrush(QColor(0, 0, 0, int(0.05 * 255)))
                else:
                    # Hover overlay: white at 6% opacity, scaled by animation
                    alpha = int(0.06 * 255 * self._hover_opacity)
                    painter.setBrush(QColor(255, 255, 255, alpha))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rect, radius, radius)
            finally:
                painter.end()
