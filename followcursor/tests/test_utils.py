"""Tests for app.utils — fmt_time, encoder profiles, build_encoder_args."""

import pytest
from unittest.mock import patch

from app.utils import (
    fmt_time,
    ENCODER_PROFILES,
    build_encoder_args,
    encoder_display_name,
    best_hw_encoder,
    detect_available_encoders,
)


# ── fmt_time ────────────────────────────────────────────────────────


class TestFmtTime:
    def test_zero(self) -> None:
        assert fmt_time(0) == "0:00"

    def test_under_one_minute(self) -> None:
        assert fmt_time(5000) == "0:05"

    def test_one_minute(self) -> None:
        assert fmt_time(60000) == "1:00"

    def test_multi_minute(self) -> None:
        assert fmt_time(125000) == "2:05"

    def test_large_value(self) -> None:
        assert fmt_time(3600000) == "60:00"

    def test_fractional_ms(self) -> None:
        # 1500.7ms → 1s
        assert fmt_time(1500.7) == "0:01"

    def test_pads_seconds(self) -> None:
        assert fmt_time(3000) == "0:03"  # "03" not "3"


# ── ENCODER_PROFILES ────────────────────────────────────────────────


class TestEncoderProfiles:
    def test_all_required_keys(self) -> None:
        expected = {"h264_nvenc", "h264_qsv", "h264_amf", "libx264"}
        assert set(ENCODER_PROFILES.keys()) == expected

    def test_profile_structure(self) -> None:
        for enc_id, (name, codec, args) in ENCODER_PROFILES.items():
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(codec, str)
            assert isinstance(args, list)

    def test_libx264_is_software(self) -> None:
        name, codec, _ = ENCODER_PROFILES["libx264"]
        assert "x264" in codec
        assert "Software" in name


# ── build_encoder_args ──────────────────────────────────────────────


class TestBuildEncoderArgs:
    def test_known_encoder(self) -> None:
        args = build_encoder_args("libx264")
        assert "-c:v" in args
        assert "libx264" in args
        assert "-pix_fmt" in args
        assert "yuv420p" in args

    def test_nvenc_args(self) -> None:
        args = build_encoder_args("h264_nvenc")
        assert "h264_nvenc" in args
        assert "-pix_fmt" in args

    def test_unknown_encoder_falls_back(self) -> None:
        """Unknown encoder ID should fall back to libx264."""
        args = build_encoder_args("nonexistent_encoder")
        assert "libx264" in args

    def test_args_always_end_with_pix_fmt(self) -> None:
        for enc_id in ENCODER_PROFILES:
            args = build_encoder_args(enc_id)
            # Last two should be -pix_fmt yuv420p
            assert args[-2:] == ["-pix_fmt", "yuv420p"]


# ── encoder_display_name ────────────────────────────────────────────


class TestEncoderDisplayName:
    def test_known(self) -> None:
        assert encoder_display_name("h264_nvenc") == "NVIDIA NVENC"
        assert encoder_display_name("libx264") == "Software (x264)"

    def test_unknown_returns_raw_id(self) -> None:
        assert encoder_display_name("unknown_codec") == "unknown_codec"


# ── detect_available_encoders / best_hw_encoder ─────────────────────


class TestEncoderDetection:
    def test_libx264_always_present(self) -> None:
        """libx264 must always be in the available list (software fallback)."""
        # Reset cache to force re-detection
        import app.utils
        app.utils._available_encoders = None
        encoders = detect_available_encoders()
        assert "libx264" in encoders
        # Reset cache
        app.utils._available_encoders = None

    def test_best_hw_encoder_returns_string(self) -> None:
        import app.utils
        app.utils._available_encoders = None
        enc = best_hw_encoder()
        assert isinstance(enc, str)
        assert enc in ENCODER_PROFILES
        app.utils._available_encoders = None

    def test_detection_caching(self) -> None:
        """Second call should return cached result."""
        import app.utils
        app.utils._available_encoders = None
        first = detect_available_encoders()
        second = detect_available_encoders()
        assert first is second  # same object (cached)
        app.utils._available_encoders = None

    def test_probe_failure_still_has_libx264(self) -> None:
        """If ffmpeg probe fails, libx264 should still be available."""
        import app.utils
        app.utils._available_encoders = None
        with patch("app.utils.ffmpeg_exe", side_effect=Exception("no ffmpeg")):
            encoders = detect_available_encoders()
            assert encoders == ["libx264"]
        app.utils._available_encoders = None
