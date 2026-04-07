"""Fluent 2 visual effects — drop shadows, hover animations, focus rings.

Reusable helpers that apply Windows 11 Fluent 2 visual polish to widgets.
All design values come from :mod:`followcursor.app.tokens`.
"""

import logging
from typing import Any, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    Property,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QWidget,
)

from . import tokens as T

logger = logging.getLogger(__name__)

# ── Drop Shadows ────────────────────────────────────────────────────────
# Fluent 2 elevation system with 7 layers (0-6) matching official spec

_SHADOW_LEVELS = {
    # Layer 0: No shadow (flat surfaces)
    "layer0": {
        "blur": T.SHADOW_LAYER_0_BLUR,
        "offset": T.SHADOW_LAYER_0_OFFSET_Y,
        "color": T.SHADOW_LAYER_0_KEY,
    },
    # Layer 1 (Shadow2): Minimal depth — buttons at rest, subtle cards
    "layer1": {
        "blur": T.SHADOW_LAYER_1_BLUR,
        "offset": T.SHADOW_LAYER_1_OFFSET_Y,
        "color": T.SHADOW_LAYER_1_KEY,
    },
    # Layer 2 (Shadow4): Cards, grid items, list items
    "layer2": {
        "blur": T.SHADOW_LAYER_2_BLUR,
        "offset": T.SHADOW_LAYER_2_OFFSET_Y,
        "color": T.SHADOW_LAYER_2_KEY,
    },
    # Layer 3 (Shadow8): Command bars, tooltips, dropdowns
    "layer3": {
        "blur": T.SHADOW_LAYER_3_BLUR,
        "offset": T.SHADOW_LAYER_3_OFFSET_Y,
        "color": T.SHADOW_LAYER_3_KEY,
    },
    # Layer 4 (Shadow16): Dialogs, callouts, flyouts
    "layer4": {
        "blur": T.SHADOW_LAYER_4_BLUR,
        "offset": T.SHADOW_LAYER_4_OFFSET_Y,
        "color": T.SHADOW_LAYER_4_KEY,
    },
    # Layer 5 (Shadow28): Modals, dialogs
    "layer5": {
        "blur": T.SHADOW_LAYER_5_BLUR,
        "offset": T.SHADOW_LAYER_5_OFFSET_Y,
        "color": T.SHADOW_LAYER_5_KEY,
    },
    # Layer 6 (Shadow64): High z-index flyouts
    "layer6": {
        "blur": T.SHADOW_LAYER_6_BLUR,
        "offset": T.SHADOW_LAYER_6_OFFSET_Y,
        "color": T.SHADOW_LAYER_6_KEY,
    },
    # Legacy aliases for backward compatibility
    "subtle": {
        "blur": T.SHADOW_LAYER_2_BLUR,
        "offset": T.SHADOW_LAYER_2_OFFSET_Y,
        "color": T.SHADOW_LAYER_2_KEY,
    },
    "medium": {
        "blur": T.SHADOW_LAYER_3_BLUR,
        "offset": T.SHADOW_LAYER_3_OFFSET_Y,
        "color": T.SHADOW_LAYER_3_KEY,
    },
}


def _parse_rgba(rgba_str: str) -> QColor:
    """Parse an 'rgba(r, g, b, a)' string into a QColor."""
    inner = rgba_str.strip().removeprefix("rgba(").removesuffix(")")
    parts = [p.strip() for p in inner.split(",")]
    return QColor(int(parts[0]), int(parts[1]), int(parts[2]),
                  int(float(parts[3]) * 255))


def apply_shadow(widget: QWidget, level: str = "layer2") -> None:
    """Apply a Fluent 2 drop shadow to *widget*.

    Qt's QGraphicsDropShadowEffect only supports a single shadow, so we use
    the key shadow (stronger component) from the Fluent 2 spec. Ambient shadow
    tokens are available in tokens.py for future custom renderers that can
    composite multiple shadow layers.

    Parameters
    ----------
    widget:
        The target widget.  An existing ``QGraphicsDropShadowEffect`` is
        replaced if present.
    level:
        Shadow elevation layer — one of:
        - ``'layer0'``: No shadow (flat)
        - ``'layer1'``: Minimal depth (buttons at rest, subtle cards)
        - ``'layer2'`` (default): Cards, grid items, list items
        - ``'layer3'``: Command bars, tooltips, dropdowns
        - ``'layer4'``: Dialogs, callouts, flyouts
        - ``'layer5'``: Modals, dialogs
        - ``'layer6'``: High z-index flyouts
        - ``'subtle'``: Legacy alias for layer2
        - ``'medium'``: Legacy alias for layer3
    """
    cfg = _SHADOW_LEVELS.get(level)
    if cfg is None:
        logger.warning("Unknown shadow level %r — skipping", level)
        return

    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(cfg["blur"])
    effect.setOffset(0, cfg["offset"])
    effect.setColor(_parse_rgba(cfg["color"]))
    widget.setGraphicsEffect(effect)


# ── Hover Animations ───────────────────────────────────────────────────

class HoverAnimationFilter(QObject):
    """Event filter that animates a widget property on hover enter / leave.

    Attach to any widget to get a smooth Fluent 2 ease-out transition
    without subclassing.  The widget must expose the target property as
    a Qt dynamic property (set with ``setProperty``).

    Usage::

        btn = QPushButton("Click me")
        install_hover_animation(btn, "_bg_opacity", 0.0, 1.0, duration_ms=100)

    For background-colour transitions, use :func:`install_hover_bg_animation`
    which sets up the ``QColor`` property and animation automatically.
    """

    def __init__(
        self,
        target: QWidget,
        prop_name: str,
        normal_val: Any,
        hover_val: Any,
        duration_ms: int = T.DURATION_FASTER,
        easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent or target)
        self._target = target
        self._prop = prop_name
        self._normal = normal_val
        self._hover = hover_val

        self._anim = QPropertyAnimation(target, prop_name.encode(), self)
        self._anim.setDuration(duration_ms)
        self._anim.setEasingCurve(easing)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is not self._target:
            return False
        if event.type() == QEvent.Type.Enter:
            self._animate(self._hover)
        elif event.type() == QEvent.Type.Leave:
            self._animate(self._normal)
        return False

    def _animate(self, end_val: Any) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._target.property(self._prop))
        self._anim.setEndValue(end_val)
        self._anim.start()


def install_hover_animation(
    widget: QWidget,
    prop_name: str,
    normal_val: Any,
    hover_val: Any,
    duration_ms: int = T.DURATION_FASTER,
    easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
) -> HoverAnimationFilter:
    """Install a hover-state animation on *widget*.

    Parameters
    ----------
    widget:
        Target widget.
    prop_name:
        Qt property name to animate (must be set via ``setProperty``).
    normal_val / hover_val:
        Start and end values for the property animation.
    duration_ms:
        Transition duration (default: ``DURATION_FASTER`` = 100 ms).
    easing:
        Easing curve type (default: ``OutCubic`` for Fluent 2 curveEasyEase).

    Returns the installed :class:`HoverAnimationFilter` so callers can
    keep a reference if needed.
    """
    widget.setProperty(prop_name, normal_val)
    filt = HoverAnimationFilter(
        widget, prop_name, normal_val, hover_val, duration_ms, easing,
    )
    widget.installEventFilter(filt)
    return filt


def install_hover_bg_animation(
    widget: QWidget,
    normal_color: str = T.BG_INTERACTIVE,
    hover_color: str = T.BG_HOVER,
    duration_ms: int = T.DURATION_FASTER,
    easing: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
) -> HoverAnimationFilter:
    """Install a hover background-colour animation on *widget*.

    Convenience wrapper around :func:`install_hover_animation` for the
    common case of transitioning a background ``QColor`` on mouse enter /
    leave.

    Parameters
    ----------
    widget:
        Target widget.
    normal_color:
        CSS hex colour for the resting state (default: ``BG_INTERACTIVE``).
    hover_color:
        CSS hex colour for the hovered state (default: ``BG_HOVER``).
    duration_ms:
        Transition duration (default: ``DURATION_FASTER`` = 100 ms).
    easing:
        Easing curve type (default: ``OutCubic`` for Fluent 2 curveEasyEase).

    Returns the installed :class:`HoverAnimationFilter`.
    """
    return install_hover_animation(
        widget,
        "_bg_color",
        QColor(normal_color),
        QColor(hover_color),
        duration_ms,
        easing,
    )


# ── Focus Ring ──────────────────────────────────────────────────────────

def apply_focus_shadow(widget: QWidget) -> None:
    """Apply a Fluent 2 focus indicator using a coloured glow effect.

    Since QSS ``outline`` support is limited in Qt, this creates a brand-
    coloured shadow around the widget to simulate a 2 px focus ring.  The
    effect is set but **disabled** by default — enable it in a focus-in
    event and disable on focus-out, or use :func:`install_focus_ring`.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(6)
    effect.setOffset(0, 0)
    color = QColor(T.BRAND)
    color.setAlpha(180)
    effect.setColor(color)
    effect.setEnabled(False)
    widget.setGraphicsEffect(effect)


class FocusRingFilter(QObject):
    """Event filter that toggles a glow shadow on focus-in / focus-out."""

    def __init__(self, target: QWidget, parent: Optional[QObject] = None) -> None:
        super().__init__(parent or target)
        self._target = target

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is not self._target:
            return False
        effect = self._target.graphicsEffect()
        if effect is None:
            return False
        if event.type() == QEvent.Type.FocusIn:
            effect.setEnabled(True)
        elif event.type() == QEvent.Type.FocusOut:
            effect.setEnabled(False)
        return False


def install_focus_ring(widget: QWidget) -> FocusRingFilter:
    """Install a Fluent 2 focus ring on *widget*.

    Adds a brand-coloured glow effect that toggles on keyboard focus.
    Returns the installed event filter.

    Note: Because ``QGraphicsDropShadowEffect`` is exclusive (only one
    per widget), this should *not* be combined with :func:`apply_shadow`
    on the same widget.  Prefer this on buttons / inputs where keyboard
    accessibility matters, and :func:`apply_shadow` on passive surfaces
    (cards, panels).
    """
    apply_focus_shadow(widget)
    filt = FocusRingFilter(widget)
    widget.installEventFilter(filt)
    return filt


# ── Fluent 2 Motion Helpers ────────────────────────────────────────────

def get_entering_curve() -> QEasingCurve.Type:
    """Return the Fluent 2 easing curve for entering elements.
    
    Maps to Fluent 2 ``curveDecelerate`` — elements slow down as they
    arrive in the viewport, creating a natural settling motion.
    """
    return QEasingCurve.Type.OutQuad


def get_exiting_curve() -> QEasingCurve.Type:
    """Return the Fluent 2 easing curve for exiting elements.
    
    Maps to Fluent 2 ``curveAccelerate`` — elements speed up as they
    leave the viewport, creating a quick exit.
    """
    return QEasingCurve.Type.InQuad


def get_default_curve() -> QEasingCurve.Type:
    """Return the default Fluent 2 easing curve for in-viewport motion.
    
    Maps to Fluent 2 ``curveEasyEase`` — smooth repositioning and state
    transitions within the viewport.
    """
    return QEasingCurve.Type.OutCubic

