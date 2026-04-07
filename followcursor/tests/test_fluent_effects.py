"""Tests for fluent_effects — Fluent 2 visual helpers (shadows, hover, focus)."""

import pytest

from app import tokens as T
from app.fluent_effects import (
    _SHADOW_LEVELS,
    _parse_rgba,
    apply_shadow,
    install_hover_animation,
    HoverAnimationFilter,
    install_focus_ring,
    FocusRingFilter,
    apply_focus_shadow,
)


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
