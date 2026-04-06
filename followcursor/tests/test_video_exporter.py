"""Tests for video_exporter geometry calculations.

Tests the GeometryComputer class and phase methods without requiring
Qt or actual video files.
"""

import pytest
import numpy as np

from app.video_exporter import GeometryComputer, VideoProbeResult, GeometryResult
from app.frames import FramePreset, DEFAULT_FRAME, FRAME_PRESETS
from app.backgrounds import PRESETS as BACKGROUND_PRESETS


# Helper to create a "No Frame" preset
def _no_frame_preset() -> FramePreset:
    """Create a No Frame preset for testing."""
    return FramePreset(
        name="None",
        bezel_width=0,
        outer_radius=0,
        inner_radius=0,
        bezel_color=(0, 0, 0),
        edge_color=(0, 0, 0),
        edge_width=0,
        show_camera=False,
        shadow_layers=0,
        padding=0.0,
    )


class TestGeometryComputer:
    """Test the GeometryComputer pure-logic class."""

    def test_no_frame_mode_landscape(self):
        """No-frame mode with landscape video should center video on canvas."""
        # 1920x1080 video on 1920x1080 canvas
        gc = GeometryComputer(
            canvas_w=1920,
            canvas_h=1080,
            src_w=1920,
            src_h=1080,
            frame_preset=_no_frame_preset(),
        )
        geom = gc.compute()

        assert geom["scr_w"] == 1920
        assert geom["scr_h"] == 1080
        assert geom["scr_x"] == 0
        assert geom["scr_y"] == 0
        # No device keys in no-frame mode
        assert "dev_x" not in geom

    def test_no_frame_mode_portrait_video_landscape_canvas(self):
        """Portrait video on landscape canvas should be centered with pillarbox."""
        gc = GeometryComputer(
            canvas_w=1920,
            canvas_h=1080,
            src_w=1080,
            src_h=1920,
            frame_preset=_no_frame_preset(),
        )
        geom = gc.compute()

        # Video should be scaled to fit height, width constrained by aspect ratio
        assert geom["scr_h"] == 1080
        # 1080 * (1080/1920) = 607.5 → 607
        assert geom["scr_w"] == 607
        # Centered horizontally
        assert geom["scr_x"] == (1920 - 607) // 2
        assert geom["scr_y"] == 0

    def test_with_frame_standard_bezel(self):
        """Standard device frame with bezel should compute correct geometry."""
        # Use the default frame preset (Laptop)
        gc = GeometryComputer(
            canvas_w=1920,
            canvas_h=1080,
            src_w=1600,
            src_h=900,
            frame_preset=DEFAULT_FRAME,
        )
        geom = gc.compute()

        # Should have device keys
        assert "dev_x" in geom
        assert "dev_y" in geom
        assert "dev_w" in geom
        assert "dev_h" in geom
        assert "bw" in geom
        assert "outer_r" in geom
        assert "inner_r" in geom
        assert "edge_thickness" in geom

        # Screen should be smaller than device (due to bezel)
        assert geom["scr_w"] < geom["dev_w"]
        assert geom["scr_h"] < geom["dev_h"]

        # Bezel width should be positive
        assert geom["bw"] > 0

        # Screen should be inside device bounds
        assert geom["scr_x"] >= geom["dev_x"]
        assert geom["scr_y"] >= geom["dev_y"]
        assert geom["scr_x"] + geom["scr_w"] <= geom["dev_x"] + geom["dev_w"]
        assert geom["scr_y"] + geom["scr_h"] <= geom["dev_y"] + geom["dev_h"]

    def test_with_frame_aspect_ratio_preserved(self):
        """Device frame should preserve video aspect ratio."""
        video_aspect = 16 / 9
        gc = GeometryComputer(
            canvas_w=1920,
            canvas_h=1080,
            src_w=1600,
            src_h=900,
            frame_preset=DEFAULT_FRAME,
        )
        geom = gc.compute()

        # Screen area should maintain video aspect ratio
        screen_aspect = geom["scr_w"] / max(geom["scr_h"], 1)
        assert abs(screen_aspect - video_aspect) < 0.01  # Within 1% tolerance

    def test_small_canvas_no_frame(self):
        """Small canvas should still compute valid geometry."""
        gc = GeometryComputer(
            canvas_w=640,
            canvas_h=480,
            src_w=1920,
            src_h=1080,
            frame_preset=_no_frame_preset(),
        )
        geom = gc.compute()

        # Video should fit within canvas
        assert geom["scr_w"] <= 640
        assert geom["scr_h"] <= 480
        assert geom["scr_x"] >= 0
        assert geom["scr_y"] >= 0

    def test_zero_bezel_width_frame(self):
        """Frame with zero bezel width should still compute correctly."""
        # Minimal frame (shadow-only, no bezel)
        gc = GeometryComputer(
            canvas_w=1920,
            canvas_h=1080,
            src_w=1600,
            src_h=900,
            frame_preset=FramePreset(
                name="Shadow Only",
                bezel_width=0,
                outer_radius=20,
                inner_radius=8,
                bezel_color=(0, 0, 0),
                edge_color=(0, 0, 0),
                edge_width=0,
                show_camera=False,
                shadow_layers=4,
                padding=0.08,
            ),
        )
        geom = gc.compute()

        # Should have device keys even with zero bezel
        assert "dev_x" in geom
        assert geom["bw"] == 0
        # Screen and device dimensions should be very close (only padding matters)
        assert abs(geom["scr_w"] - geom["dev_w"]) < 5

    def test_high_padding_frame(self):
        """High padding should leave space around device."""
        gc = GeometryComputer(
            canvas_w=1920,
            canvas_h=1080,
            src_w=1600,
            src_h=900,
            frame_preset=FramePreset(
                name="Padded",
                bezel_width=40,
                outer_radius=20,
                inner_radius=8,
                bezel_color=(26, 26, 26),
                edge_color=(107, 107, 107),
                edge_width=2,
                show_camera=False,
                shadow_layers=4,
                padding=0.15,  # High padding
            ),
        )
        geom = gc.compute()

        # Device should be smaller than canvas due to padding
        padding_px = 1920 * 0.15
        assert geom["dev_x"] >= padding_px * 0.9  # Allow 10% tolerance
        assert geom["dev_y"] >= 1080 * 0.15 * 0.9


class TestVideoProbeResult:
    """Test the VideoProbeResult dataclass."""

    def test_dataclass_construction(self):
        """VideoProbeResult should construct with all fields."""
        result = VideoProbeResult(
            src_fps=30.0,
            total_frames=900,
            src_w=1920,
            src_h=1080,
            out_w=1920,
            out_h=1080,
            fps=30.0,
            is_gif=False,
        )
        assert result.src_fps == 30.0
        assert result.total_frames == 900
        assert result.src_w == 1920
        assert result.src_h == 1080
        assert result.out_w == 1920
        assert result.out_h == 1080
        assert result.fps == 30.0
        assert result.is_gif is False


class TestGeometryResult:
    """Test the GeometryResult dataclass."""

    def test_dataclass_construction(self):
        """GeometryResult should construct with required fields."""
        # Create dummy numpy arrays
        canvas = np.zeros((1080, 1920, 3), dtype=np.uint8)
        mask = np.zeros((1080, 1920), dtype=np.uint8)
        bg = np.zeros((1080, 1920, 3), dtype=np.uint8)

        result = GeometryResult(
            scr_x=100,
            scr_y=100,
            scr_w=1720,
            scr_h=880,
            base_canvas=canvas,
            screen_mask=mask,
            device_mask_u8=None,
            bg=bg,
        )
        assert result.scr_x == 100
        assert result.scr_y == 100
        assert result.scr_w == 1720
        assert result.scr_h == 880
        assert result.base_canvas.shape == (1080, 1920, 3)
        assert result.screen_mask.shape == (1080, 1920)
        assert result.device_mask_u8 is None
        assert result.bg.shape == (1080, 1920, 3)


class TestIntegrationScenarios:
    """Integration tests combining geometry computation with realistic scenarios."""

    def test_4k_export_with_laptop_frame(self):
        """4K export with laptop frame should compute valid geometry."""
        gc = GeometryComputer(
            canvas_w=3840,
            canvas_h=2160,
            src_w=2560,
            src_h=1440,
            frame_preset=DEFAULT_FRAME,
        )
        geom = gc.compute()

        # Should fit within 4K canvas
        assert geom["scr_x"] + geom["scr_w"] <= 3840
        assert geom["scr_y"] + geom["scr_h"] <= 2160
        # Device should be visible (not zero-sized)
        assert geom["dev_w"] > 0
        assert geom["dev_h"] > 0

    def test_gif_export_small_canvas(self):
        """GIF export with smaller canvas (800x600) should work."""
        gc = GeometryComputer(
            canvas_w=800,
            canvas_h=600,
            src_w=1920,
            src_h=1080,
            frame_preset=_no_frame_preset(),
        )
        geom = gc.compute()

        # Video should be downscaled to fit
        assert geom["scr_w"] <= 800
        assert geom["scr_h"] <= 600

    def test_all_frame_presets_valid(self):
        """All frame presets should produce valid geometry."""
        for preset in FRAME_PRESETS:
            gc = GeometryComputer(
                canvas_w=1920,
                canvas_h=1080,
                src_w=1600,
                src_h=900,
                frame_preset=preset,
            )
            geom = gc.compute()

            # Basic validity checks
            assert geom["scr_w"] > 0
            assert geom["scr_h"] > 0
            assert geom["scr_x"] >= 0
            assert geom["scr_y"] >= 0
            assert geom["scr_x"] + geom["scr_w"] <= 1920
            assert geom["scr_y"] + geom["scr_h"] <= 1080
