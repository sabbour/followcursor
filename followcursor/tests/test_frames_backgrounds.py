"""Tests for app.frames and app.backgrounds — preset data & serialization."""

import pytest

from app.frames import FramePreset, FRAME_PRESETS, DEFAULT_FRAME
from app.backgrounds import (
    BackgroundPreset,
    PRESETS as BG_PRESETS,
    DEFAULT_PRESET as BG_DEFAULT,
    SOLID_PRESETS,
    GRADIENT_PRESETS,
    PATTERN_PRESETS,
    WAVE_LAYERS,
    CAT_SOLID,
    CAT_GRADIENT,
    CAT_PATTERN,
    CATEGORIES,
)


# ── FramePreset ─────────────────────────────────────────────────────


class TestFramePreset:
    def test_roundtrip(self) -> None:
        for fp in FRAME_PRESETS:
            d = fp.to_dict()
            fp2 = FramePreset.from_dict(d)
            assert fp2.name == fp.name
            assert fp2.bezel_width == fp.bezel_width
            assert fp2.outer_radius == fp.outer_radius
            assert fp2.inner_radius == fp.inner_radius
            assert fp2.bezel_color == fp.bezel_color
            assert fp2.edge_color == fp.edge_color
            assert fp2.edge_width == fp.edge_width
            assert fp2.show_camera == fp.show_camera
            assert fp2.shadow_layers == fp.shadow_layers
            assert fp2.padding == fp.padding

    def test_preset_count(self) -> None:
        assert len(FRAME_PRESETS) == 5

    def test_default_is_wide_bezel(self) -> None:
        assert DEFAULT_FRAME.name == "Wide Bezel"

    def test_no_frame_is_none(self) -> None:
        no_frame = [fp for fp in FRAME_PRESETS if fp.name == "No Frame"]
        assert len(no_frame) == 1
        assert no_frame[0].is_none

    def test_wide_bezel_is_not_none(self) -> None:
        assert not DEFAULT_FRAME.is_none

    def test_shadow_only_is_not_none(self) -> None:
        """Shadow Only has bezel_width=0 but shadow_layers>0 → is_none=False."""
        shadow = [fp for fp in FRAME_PRESETS if fp.name == "Shadow Only"]
        assert len(shadow) == 1
        assert not shadow[0].is_none

    def test_dict_keys(self) -> None:
        d = DEFAULT_FRAME.to_dict()
        expected = {
            "name", "bezel_width", "outer_radius", "inner_radius",
            "bezel_color", "edge_color", "edge_width",
            "show_camera", "shadow_layers", "padding",
        }
        assert set(d.keys()) == expected

    def test_colors_are_tuples_after_roundtrip(self) -> None:
        """from_dict should convert color lists back to tuples."""
        d = DEFAULT_FRAME.to_dict()
        assert isinstance(d["bezel_color"], list)  # to_dict → list
        fp = FramePreset.from_dict(d)
        assert isinstance(fp.bezel_color, tuple)
        assert isinstance(fp.edge_color, tuple)

    def test_unique_names(self) -> None:
        names = [fp.name for fp in FRAME_PRESETS]
        assert len(names) == len(set(names))


# ── BackgroundPreset ────────────────────────────────────────────────


class TestBackgroundPreset:
    def test_roundtrip(self) -> None:
        for bp in BG_PRESETS:
            d = bp.to_dict()
            bp2 = BackgroundPreset.from_dict(d)
            assert bp2.name == bp.name
            assert bp2.kind == bp.kind
            assert bp2.color_top == bp.color_top
            assert bp2.color_bottom == bp.color_bottom

    def test_preset_count_minimum(self) -> None:
        """Should have a substantial number of presets."""
        assert len(BG_PRESETS) >= 80

    def test_default_is_pure_white(self) -> None:
        assert BG_DEFAULT.name == "Pure White"

    def test_category_auto_assignment(self) -> None:
        """__post_init__ should auto-assign category based on kind."""
        solid = BackgroundPreset("test", "solid", (0, 0, 0), (0, 0, 0))
        assert solid.category == "solid"

        grad = BackgroundPreset("test", "gradient", (0, 0, 0), (0, 0, 0))
        assert grad.category == "gradient"

        radial = BackgroundPreset("test", "radial", (0, 0, 0), (0, 0, 0))
        assert radial.category == "gradient"

        spotlight = BackgroundPreset("test", "spotlight", (0, 0, 0), (0, 0, 0))
        assert spotlight.category == "gradient"

        wavy = BackgroundPreset("test", "wavy", (0, 0, 0), (0, 0, 0))
        assert wavy.category == "pattern"

    def test_is_gradient(self) -> None:
        grad = BackgroundPreset("t", "gradient", (0, 0, 0), (0, 0, 0))
        radial = BackgroundPreset("t", "radial", (0, 0, 0), (0, 0, 0))
        assert grad.is_gradient
        assert not radial.is_gradient  # radial is gradient category but not "gradient" kind

    def test_is_wavy(self) -> None:
        wavy = BackgroundPreset("t", "wavy", (0, 0, 0), (0, 0, 0))
        solid = BackgroundPreset("t", "solid", (0, 0, 0), (0, 0, 0))
        assert wavy.is_wavy
        assert not solid.is_wavy

    def test_is_pattern(self) -> None:
        wavy = BackgroundPreset("t", "wavy", (0, 0, 0), (0, 0, 0))
        assert wavy.is_pattern

    def test_category_lists_partition(self) -> None:
        """SOLID + GRADIENT + PATTERN should cover all presets."""
        total = len(SOLID_PRESETS) + len(GRADIENT_PRESETS) + len(PATTERN_PRESETS)
        assert total == len(BG_PRESETS)

    def test_solid_presets_are_solid(self) -> None:
        for bp in SOLID_PRESETS:
            assert bp.kind == "solid"
            assert bp.category == CAT_SOLID

    def test_gradient_presets_are_gradient_category(self) -> None:
        for bp in GRADIENT_PRESETS:
            assert bp.kind in ("gradient", "radial", "spotlight")
            assert bp.category == CAT_GRADIENT

    def test_pattern_presets_are_pattern(self) -> None:
        for bp in PATTERN_PRESETS:
            assert bp.kind == "wavy"
            assert bp.category == CAT_PATTERN

    def test_colors_are_tuples_after_roundtrip(self) -> None:
        d = BG_DEFAULT.to_dict()
        bp = BackgroundPreset.from_dict(d)
        assert isinstance(bp.color_top, tuple)
        assert isinstance(bp.color_bottom, tuple)

    def test_unique_names(self) -> None:
        names = [bp.name for bp in BG_PRESETS]
        assert len(names) == len(set(names))

    def test_dict_keys(self) -> None:
        d = BG_DEFAULT.to_dict()
        assert set(d.keys()) == {"name", "kind", "color_top", "color_bottom"}


# ── Wave layers ─────────────────────────────────────────────────────


class TestWaveLayers:
    def test_layer_count(self) -> None:
        assert len(WAVE_LAYERS) == 5

    def test_layer_structure(self) -> None:
        for layer in WAVE_LAYERS:
            assert len(layer) == 6
            y_center, amplitude, frequency, phase, alpha, use_top = layer
            assert 0.0 <= y_center <= 1.0
            assert amplitude >= 0.0
            assert frequency > 0.0
            assert 0.0 <= alpha <= 1.0
            assert isinstance(use_top, bool)


# ── Categories ──────────────────────────────────────────────────────


class TestCategories:
    def test_three_categories(self) -> None:
        assert set(CATEGORIES) == {"solid", "gradient", "pattern"}
