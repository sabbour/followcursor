"""Tests for fluent_effects — Fluent 2 visual helpers (shadows, hover, focus)."""

import pytest

from PySide6.QtWidgets import QApplication, QWidget, QPushButton
from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor

from app import tokens as T
from app.fluent_effects import (
    _SHADOW_LEVELS,
    _parse_rgba,
    apply_shadow,
    install_hover_animation,
    install_hover_bg_animation,
    HoverAnimationFilter,
    install_focus_ring,
    FocusRingFilter,
    apply_focus_shadow,
)


# ── QApplication fixture (needed for widget tests) ──────────────────

@pytest.fixture(scope="module")
def qapp():
    """Provide a QApplication instance for the module."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ── _parse_rgba ─────────────────────────────────────────────────────

class TestParseRgba:
    def test_basic(self) -> None:
        c = _parse_rgba("rgba(0, 0, 0, 0.25)")
        assert c.red() == 0
        assert c.green() == 0
        assert c.blue() == 0
        assert c.alpha() == 63  # int(0.25 * 255)

    def test_non_zero_values(self) -> None:
        c = _parse_rgba("rgba(255, 128, 64, 1.0)")
        assert c.red() == 255
        assert c.green() == 128
        assert c.blue() == 64
        assert c.alpha() == 255

    def test_shadow_subtle_color(self) -> None:
        c = _parse_rgba(T.SHADOW_SUBTLE_COLOR)
        assert c.red() == 0
        assert c.alpha() == 63

    def test_shadow_medium_color(self) -> None:
        c = _parse_rgba(T.SHADOW_MEDIUM_COLOR)
        assert c.alpha() == 89  # int(0.35 * 255)


# ── Shadow level config ─────────────────────────────────────────────

class TestShadowLevels:
    def test_subtle_exists(self) -> None:
        cfg = _SHADOW_LEVELS["subtle"]
        assert cfg["blur"] == T.SHADOW_SUBTLE_BLUR
        assert cfg["offset"] == T.SHADOW_SUBTLE_OFFSET

    def test_medium_exists(self) -> None:
        cfg = _SHADOW_LEVELS["medium"]
        assert cfg["blur"] == T.SHADOW_MEDIUM_BLUR
        assert cfg["offset"] == T.SHADOW_MEDIUM_OFFSET

    def test_only_two_levels(self) -> None:
        assert set(_SHADOW_LEVELS.keys()) == {"subtle", "medium"}


# ── apply_shadow ────────────────────────────────────────────────────

class TestApplyShadow:
    def test_subtle_shadow(self, qapp: QApplication) -> None:
        w = QWidget()
        apply_shadow(w, "subtle")
        effect = w.graphicsEffect()
        assert effect is not None
        assert effect.blurRadius() == T.SHADOW_SUBTLE_BLUR
        assert effect.offset().y() == T.SHADOW_SUBTLE_OFFSET

    def test_medium_shadow(self, qapp: QApplication) -> None:
        w = QWidget()
        apply_shadow(w, "medium")
        effect = w.graphicsEffect()
        assert effect is not None
        assert effect.blurRadius() == T.SHADOW_MEDIUM_BLUR

    def test_unknown_level_skips(self, qapp: QApplication) -> None:
        w = QWidget()
        apply_shadow(w, "nonexistent")
        assert w.graphicsEffect() is None

    def test_replaces_existing_effect(self, qapp: QApplication) -> None:
        w = QWidget()
        apply_shadow(w, "subtle")
        apply_shadow(w, "medium")
        effect = w.graphicsEffect()
        assert effect is not None
        assert effect.blurRadius() == T.SHADOW_MEDIUM_BLUR


# ── HoverAnimationFilter ───────────────────────────────────────────

class TestHoverAnimationFilter:
    def test_install_sets_property(self, qapp: QApplication) -> None:
        btn = QPushButton("Test")
        filt = install_hover_animation(btn, "_opacity", 0.0, 1.0)
        assert isinstance(filt, HoverAnimationFilter)
        assert btn.property("_opacity") == 0.0

    def test_filter_installed_on_widget(self, qapp: QApplication) -> None:
        btn = QPushButton("Test")
        filt = install_hover_animation(btn, "_opacity", 0.0, 1.0)
        # The filter should be in the event filter chain — verify via type
        assert isinstance(filt, HoverAnimationFilter)

    def test_hover_bg_animation(self, qapp: QApplication) -> None:
        btn = QPushButton("Test")
        filt = install_hover_bg_animation(btn)
        assert isinstance(filt, HoverAnimationFilter)
        prop = btn.property("_bg_color")
        assert isinstance(prop, QColor)
        assert prop == QColor(T.BG_INTERACTIVE)

    def test_hover_bg_animation_custom_colors(self, qapp: QApplication) -> None:
        btn = QPushButton("Test")
        filt = install_hover_bg_animation(
            btn, normal_color="#ff0000", hover_color="#00ff00",
        )
        assert btn.property("_bg_color") == QColor("#ff0000")


# ── install_focus_ring / FocusRingFilter ───────────────────────────

class TestFocusRing:
    def test_install_creates_effect(self, qapp: QApplication) -> None:
        btn = QPushButton("Test")
        filt = install_focus_ring(btn)
        assert isinstance(filt, FocusRingFilter)
        effect = btn.graphicsEffect()
        assert effect is not None
        assert not effect.isEnabled()

    def test_apply_focus_shadow_disabled_by_default(self, qapp: QApplication) -> None:
        w = QWidget()
        apply_focus_shadow(w)
        effect = w.graphicsEffect()
        assert effect is not None
        assert not effect.isEnabled()
        assert effect.blurRadius() == 6

    def test_focus_ring_brand_color(self, qapp: QApplication) -> None:
        btn = QPushButton("Test")
        install_focus_ring(btn)
        effect = btn.graphicsEffect()
        color = effect.color()
        # Should be brand colour with alpha
        expected = QColor(T.BRAND)
        assert color.red() == expected.red()
        assert color.green() == expected.green()
        assert color.blue() == expected.blue()
        assert color.alpha() == 180


# ── Token integrity ──────────────────────────────────────────────────

class TestTokenIntegrity:
    """Verify the new tokens added for Phase 2 exist and have valid values."""

    def test_focus_ring_width(self) -> None:
        assert T.FOCUS_RING_WIDTH == 2

    def test_focus_ring_offset(self) -> None:
        assert T.FOCUS_RING_OFFSET == 2

    def test_scrollbar_thin(self) -> None:
        assert T.SCROLLBAR_THIN == 6

    def test_scrollbar_wide(self) -> None:
        assert T.SCROLLBAR_WIDE == 12

    def test_scrollbar_min_height(self) -> None:
        assert T.SCROLLBAR_MIN_HEIGHT == 24

    def test_scrollbar_wide_gt_thin(self) -> None:
        assert T.SCROLLBAR_WIDE > T.SCROLLBAR_THIN

    def test_bg_hover_strong_exists(self) -> None:
        assert hasattr(T, "BG_HOVER_STRONG")
        assert T.BG_HOVER_STRONG != T.BG_HOVER
