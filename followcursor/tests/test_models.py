"""Tests for app.models — dataclass serialization roundtrips."""

import json
import uuid

import pytest

from app.models import (
    MousePosition,
    KeyEvent,
    ClickEvent,
    ZoomKeyframe,
    RecordingSession,
    VoiceoverSegment,
    VideoSegment,
    Chapter,
    ClickEffectPreset,
    KeystrokeOverlayConfig,
    TextAnnotation,
    ArrowAnnotation,
    HighlightBox,
    AnnotationCollection,
    DEFAULT_FPS,
    DEFAULT_MOUSE_INTERVAL,
)


# ── MousePosition ──────────────────────────────────────────────────


class TestMousePosition:
    def test_roundtrip(self) -> None:
        mp = MousePosition(x=123.5, y=456.7, timestamp=789.0)
        d = mp.to_dict()
        mp2 = MousePosition.from_dict(d)
        assert mp2.x == mp.x
        assert mp2.y == mp.y
        assert mp2.timestamp == mp.timestamp

    def test_dict_keys(self) -> None:
        d = MousePosition(x=1, y=2, timestamp=3).to_dict()
        assert set(d.keys()) == {"x", "y", "timestamp"}


# ── KeyEvent ────────────────────────────────────────────────────────


class TestKeyEvent:
    def test_roundtrip(self) -> None:
        ke = KeyEvent(timestamp=42.0)
        d = ke.to_dict()
        ke2 = KeyEvent.from_dict(d)
        assert ke2.timestamp == ke.timestamp
        assert ke2.x is None
        assert ke2.y is None

    def test_roundtrip_with_position(self) -> None:
        ke = KeyEvent(timestamp=42.0, x=960.0, y=540.0)
        d = ke.to_dict()
        ke2 = KeyEvent.from_dict(d)
        assert ke2.timestamp == ke.timestamp
        assert ke2.x == 960.0
        assert ke2.y == 540.0

    def test_dict_keys_without_position(self) -> None:
        d = KeyEvent(timestamp=0).to_dict()
        assert set(d.keys()) == {"timestamp"}

    def test_dict_keys_with_position(self) -> None:
        d = KeyEvent(timestamp=0, x=100.0, y=200.0).to_dict()
        assert set(d.keys()) == {"timestamp", "x", "y"}

    def test_from_dict_backward_compat(self) -> None:
        """Old projects without x/y in KeyEvent should still load."""
        d = {"timestamp": 99.0}
        ke = KeyEvent.from_dict(d)
        assert ke.timestamp == 99.0
        assert ke.x is None
        assert ke.y is None


# ── ClickEvent ──────────────────────────────────────────────────────


class TestClickEvent:
    def test_roundtrip(self) -> None:
        ce = ClickEvent(x=10, y=20, timestamp=30)
        d = ce.to_dict()
        ce2 = ClickEvent.from_dict(d)
        assert ce2.x == ce.x
        assert ce2.y == ce.y
        assert ce2.timestamp == ce.timestamp


# ── ZoomKeyframe ────────────────────────────────────────────────────


class TestZoomKeyframe:
    def test_create_generates_uuid(self) -> None:
        kf = ZoomKeyframe.create(timestamp=100, zoom=1.5)
        # Must be a valid UUID4
        uuid.UUID(kf.id)

    def test_create_defaults(self) -> None:
        kf = ZoomKeyframe.create(timestamp=100, zoom=1.5)
        assert kf.x == 0.5
        assert kf.y == 0.5
        assert kf.duration == 600.0
        assert kf.reason == ""

    def test_create_custom(self) -> None:
        kf = ZoomKeyframe.create(
            timestamp=200, zoom=2.0, x=0.3, y=0.7,
            duration=400, reason="test"
        )
        assert kf.timestamp == 200
        assert kf.zoom == 2.0
        assert kf.x == 0.3
        assert kf.y == 0.7
        assert kf.duration == 400
        assert kf.reason == "test"

    def test_roundtrip(self) -> None:
        kf = ZoomKeyframe.create(
            timestamp=500, zoom=1.25, x=0.2, y=0.8, duration=300, reason="r"
        )
        d = kf.to_dict()
        kf2 = ZoomKeyframe.from_dict(d)
        assert kf2.id == kf.id
        assert kf2.timestamp == kf.timestamp
        assert kf2.zoom == kf.zoom
        assert kf2.x == kf.x
        assert kf2.y == kf.y
        assert kf2.duration == kf.duration
        assert kf2.reason == kf.reason

    def test_reason_omitted_when_empty(self) -> None:
        kf = ZoomKeyframe.create(timestamp=0, zoom=1.0)
        d = kf.to_dict()
        assert "reason" not in d

    def test_from_dict_ignores_unknown_keys(self) -> None:
        d = {
            "id": "abc",
            "timestamp": 10,
            "zoom": 1.0,
            "x": 0.5,
            "y": 0.5,
            "duration": 600,
            "future_field": True,
        }
        kf = ZoomKeyframe.from_dict(d)
        assert kf.id == "abc"
        assert not hasattr(kf, "future_field")

    def test_speed_default(self) -> None:
        kf = ZoomKeyframe.create(timestamp=0, zoom=2.0)
        assert kf.speed == 1.0

    def test_speed_roundtrip(self) -> None:
        kf = ZoomKeyframe.create(timestamp=100, zoom=2.0, speed=2.5)
        d = kf.to_dict()
        assert d["speed"] == 2.5
        kf2 = ZoomKeyframe.from_dict(d)
        assert kf2.speed == 2.5

    def test_speed_omitted_when_default(self) -> None:
        kf = ZoomKeyframe.create(timestamp=0, zoom=1.0)
        d = kf.to_dict()
        assert "speed" not in d

    def test_speed_backward_compat(self) -> None:
        d = {"id": "abc", "timestamp": 10, "zoom": 2.0, "x": 0.5, "y": 0.5, "duration": 600}
        kf = ZoomKeyframe.from_dict(d)
        assert kf.speed == 1.0

    def test_speed_clamped_for_invalid_values(self) -> None:
        """Speed ≤ 0 or non-numeric → default 1.0; > 10 → clamped to 10."""
        base = {"id": "abc", "timestamp": 10, "zoom": 2.0, "x": 0.5, "y": 0.5, "duration": 600}
        cases = [
            # (input_speed, expected_speed)
            (-100.0, 1.0),   # far below valid range
            (-1.0, 1.0),     # negative
            (0, 1.0),        # zero (would cause division-by-zero)
            ("fast", 1.0),   # non-numeric string
            (None, 1.0),     # None
            (99.0, 10.0),    # above max
            (10.1, 10.0),    # just above max
        ]
        for speed_in, expected in cases:
            d = {**base, "speed": speed_in}
            kf = ZoomKeyframe.from_dict(d)
            assert kf.speed == expected, (
                f"speed={speed_in!r} should become {expected}, got {kf.speed}"
            )

    def test_speed_preserved_for_valid_values(self) -> None:
        """Valid speeds in (0, 10] must survive from_dict roundtrip."""
        base = {"id": "abc", "timestamp": 10, "zoom": 2.0, "x": 0.5, "y": 0.5, "duration": 600}
        for speed_in in [0.5, 1.0, 1.5, 5.0, 9.99, 10.0]:
            d = {**base, "speed": speed_in}
            kf = ZoomKeyframe.from_dict(d)
            assert kf.speed == speed_in, (
                f"valid speed={speed_in} should be preserved, got {kf.speed}"
            )


# ── RecordingSession ────────────────────────────────────────────────


class TestRecordingSession:
    def test_json_roundtrip(self, sample_session: RecordingSession) -> None:
        s = sample_session.to_json()
        s2 = RecordingSession.from_json(s)
        assert s2.id == sample_session.id
        assert s2.start_time == sample_session.start_time
        assert s2.duration == sample_session.duration
        assert len(s2.mouse_track) == len(sample_session.mouse_track)
        assert len(s2.keyframes) == len(sample_session.keyframes)

    def test_json_includes_key_events(self, sample_session: RecordingSession) -> None:
        s = sample_session.to_json()
        d = json.loads(s)
        assert "keyEvents" in d
        assert len(d["keyEvents"]) == 2

    def test_json_includes_click_events(self, sample_session: RecordingSession) -> None:
        s = sample_session.to_json()
        d = json.loads(s)
        assert "clickEvents" in d
        assert len(d["clickEvents"]) == 1

    def test_json_includes_frame_timestamps(self, sample_session: RecordingSession) -> None:
        s = sample_session.to_json()
        d = json.loads(s)
        assert "frameTimestamps" in d
        assert len(d["frameTimestamps"]) == 20

    def test_json_includes_trim(self, sample_session: RecordingSession) -> None:
        s = sample_session.to_json()
        d = json.loads(s)
        assert d["trimStartMs"] == 32.0
        assert d["trimEndMs"] == 288.0

    def test_json_omits_defaults(self) -> None:
        """Optional fields should be absent when they hold default values."""
        session = RecordingSession(
            id="bare",
            start_time=0,
            duration=100,
            mouse_track=[MousePosition(0, 0, 0)],
            keyframes=[],
        )
        d = json.loads(session.to_json())
        assert "keyEvents" not in d
        assert "clickEvents" not in d
        assert "frameTimestamps" not in d
        assert "trimStartMs" not in d
        assert "trimEndMs" not in d

    def test_roundtrip_preserves_mouse_positions(self, sample_session: RecordingSession) -> None:
        s2 = RecordingSession.from_json(sample_session.to_json())
        for orig, loaded in zip(sample_session.mouse_track, s2.mouse_track):
            assert orig.x == loaded.x
            assert orig.y == loaded.y
            assert orig.timestamp == loaded.timestamp

    def test_roundtrip_preserves_keyframe_fields(self, sample_session: RecordingSession) -> None:
        s2 = RecordingSession.from_json(sample_session.to_json())
        for orig, loaded in zip(sample_session.keyframes, s2.keyframes):
            assert orig.id == loaded.id
            assert orig.zoom == loaded.zoom

    def test_roundtrip_preserves_trim(self, sample_session: RecordingSession) -> None:
        s2 = RecordingSession.from_json(sample_session.to_json())
        assert s2.trim_start_ms == sample_session.trim_start_ms
        assert s2.trim_end_ms == sample_session.trim_end_ms

    def test_json_includes_voiceover_segments(self) -> None:
        seg = VoiceoverSegment.create(timestamp=1000, text="Hello world", voice="echo")
        session = RecordingSession(
            id="vo", start_time=0, duration=5000,
            mouse_track=[MousePosition(0, 0, 0)],
            keyframes=[],
            voiceover_segments=[seg],
        )
        d = json.loads(session.to_json())
        assert "voiceoverSegments" in d
        assert len(d["voiceoverSegments"]) == 1
        assert d["voiceoverSegments"][0]["text"] == "Hello world"

    def test_json_roundtrip_voiceover(self) -> None:
        seg = VoiceoverSegment.create(timestamp=2000, text="Test narration", voice="nova")
        session = RecordingSession(
            id="vo2", start_time=0, duration=5000,
            mouse_track=[MousePosition(0, 0, 0)],
            keyframes=[],
            voiceover_segments=[seg],
        )
        s2 = RecordingSession.from_json(session.to_json())
        assert s2.voiceover_segments is not None
        assert len(s2.voiceover_segments) == 1
        assert s2.voiceover_segments[0].text == "Test narration"
        assert s2.voiceover_segments[0].voice == "nova"
        assert s2.voiceover_segments[0].timestamp == 2000

    def test_json_omits_voiceover_when_empty(self) -> None:
        session = RecordingSession(
            id="bare2", start_time=0, duration=100,
            mouse_track=[MousePosition(0, 0, 0)],
            keyframes=[],
        )
        d = json.loads(session.to_json())
        assert "voiceoverSegments" not in d


# ── VoiceoverSegment ────────────────────────────────────────────────


class TestVoiceoverSegment:
    def test_create_generates_uuid(self) -> None:
        seg = VoiceoverSegment.create(timestamp=1000, text="Hello")
        assert seg.id
        uuid.UUID(seg.id)  # validates format

    def test_create_defaults(self) -> None:
        seg = VoiceoverSegment.create(timestamp=500, text="Test")
        assert seg.voice == "en-US-Ava:DragonHDLatestNeural"
        assert seg.audio_path == ""
        assert seg.duration_ms == 0.0
        assert seg.rate == 1.0
        assert seg.volume == 1.0

    def test_roundtrip(self) -> None:
        seg = VoiceoverSegment.create(timestamp=1500, text="Test text", voice="echo")
        d = seg.to_dict()
        seg2 = VoiceoverSegment.from_dict(d)
        assert seg2.id == seg.id
        assert seg2.timestamp == seg.timestamp
        assert seg2.text == seg.text
        assert seg2.voice == seg.voice

    def test_dict_omits_zero_duration(self) -> None:
        seg = VoiceoverSegment.create(timestamp=0, text="Test")
        d = seg.to_dict()
        assert "durationMs" not in d

    def test_dict_includes_nonzero_duration(self) -> None:
        seg = VoiceoverSegment.create(timestamp=0, text="Test")
        seg.duration_ms = 3000.0
        d = seg.to_dict()
        assert d["durationMs"] == 3000.0

    def test_from_dict_backward_compat(self) -> None:
        d = {"id": "abc", "timestamp": 100, "text": "Hi"}
        seg = VoiceoverSegment.from_dict(d)
        assert seg.voice == "en-US-Ava:DragonHDLatestNeural"
        assert seg.duration_ms == 0.0
        assert seg.rate == 1.0
        assert seg.volume == 1.0

    def test_rate_clamped_for_invalid_values(self) -> None:
        """Rate must be clamped to [0.0, 3.0]; non-numeric falls back to 1.0."""
        base = {"id": "abc", "timestamp": 100, "text": "Hi"}
        cases = [
            (-1.0, 0.0),     # negative → 0.0
            (0.0, 0.0),      # zero is valid lower bound
            (3.0, 3.0),      # max valid value
            (3.1, 3.0),      # just above max → clamped
            (10.0, 3.0),     # far above max → clamped
            ("fast", 1.0),   # non-numeric → default
            (None, 1.0),     # None → default
        ]
        for rate_in, expected in cases:
            d = {**base, "rate": rate_in}
            seg = VoiceoverSegment.from_dict(d)
            assert seg.rate == expected, (
                f"rate={rate_in!r} should become {expected}, got {seg.rate}"
            )

    def test_volume_clamped_for_invalid_values(self) -> None:
        """Volume must be clamped to [0.0, 3.0]; non-numeric falls back to 1.0."""
        base = {"id": "abc", "timestamp": 100, "text": "Hi"}
        cases = [
            (-0.5, 0.0),     # negative → 0.0
            (0.0, 0.0),      # zero is valid (mute)
            (3.0, 3.0),      # max valid value
            (5.0, 3.0),      # above max → clamped
            ("loud", 1.0),   # non-numeric → default
            (None, 1.0),     # None → default
        ]
        for vol_in, expected in cases:
            d = {**base, "volume": vol_in}
            seg = VoiceoverSegment.from_dict(d)
            assert seg.volume == expected, (
                f"volume={vol_in!r} should become {expected}, got {seg.volume}"
            )


# ── VideoSegment ────────────────────────────────────────────────────


class TestVideoSegment:
    def test_create_generates_uuid(self) -> None:
        seg = VideoSegment.create(start_ms=0, end_ms=5000)
        assert seg.id
        uuid.UUID(seg.id)  # validates format

    def test_create_defaults(self) -> None:
        seg = VideoSegment.create(start_ms=1000, end_ms=3000)
        assert seg.start_ms == 1000
        assert seg.end_ms == 3000
        assert seg.speed == 1.0

    def test_create_custom_speed(self) -> None:
        seg = VideoSegment.create(start_ms=0, end_ms=5000, speed=2.0)
        assert seg.speed == 2.0

    def test_roundtrip(self) -> None:
        seg = VideoSegment.create(start_ms=100, end_ms=4000, speed=0.5)
        d = seg.to_dict()
        seg2 = VideoSegment.from_dict(d)
        assert seg2.id == seg.id
        assert seg2.start_ms == seg.start_ms
        assert seg2.end_ms == seg.end_ms
        assert seg2.speed == seg.speed

    def test_dict_omits_default_speed(self) -> None:
        seg = VideoSegment.create(start_ms=0, end_ms=5000)
        d = seg.to_dict()
        assert "speed" not in d

    def test_dict_includes_nondefault_speed(self) -> None:
        seg = VideoSegment.create(start_ms=0, end_ms=5000, speed=1.5)
        d = seg.to_dict()
        assert d["speed"] == 1.5

    def test_from_dict_backward_compat(self) -> None:
        d = {"id": "abc", "startMs": 0, "endMs": 5000}
        seg = VideoSegment.from_dict(d)
        assert seg.speed == 1.0

    def test_speed_clamped_for_invalid_values(self) -> None:
        """Speed ≤ 0 → clamped to 0.1; non-numeric → default 1.0; > 10 → clamped to 10."""
        base = {"id": "abc", "startMs": 0, "endMs": 5000}
        cases = [
            (0.0, 0.1),      # zero → minimum (prevents division-by-zero)
            (-1.0, 0.1),     # negative → minimum
            (-100.0, 0.1),   # far below valid range → minimum
            ("fast", 1.0),   # non-numeric string → default 1.0
            (None, 1.0),     # None → default 1.0
            (99.0, 10.0),    # above max → clamped to 10
            (10.1, 10.0),    # just above max → clamped to 10
        ]
        for speed_in, expected in cases:
            d = {**base, "speed": speed_in}
            seg = VideoSegment.from_dict(d)
            assert seg.speed == expected, (
                f"speed={speed_in!r} should become {expected}, got {seg.speed}"
            )

    def test_speed_preserved_for_valid_values(self) -> None:
        """Valid speeds in [0.1, 10.0] must survive from_dict roundtrip."""
        base = {"id": "abc", "startMs": 0, "endMs": 5000}
        for speed_in in [0.1, 0.5, 1.0, 2.0, 5.0, 9.99, 10.0]:
            d = {**base, "speed": speed_in}
            seg = VideoSegment.from_dict(d)
            assert seg.speed == speed_in, (
                f"valid speed={speed_in} should be preserved, got {seg.speed}"
            )


# ── RecordingSession + VideoSegments ─────────────────────────────────


class TestRecordingSessionVideoSegments:
    def test_json_includes_video_segments(self) -> None:
        seg = VideoSegment.create(start_ms=0, end_ms=5000)
        session = RecordingSession(
            id="vs1", start_time=0, duration=5000,
            mouse_track=[MousePosition(0, 0, 0)],
            keyframes=[],
            video_segments=[seg],
        )
        d = json.loads(session.to_json())
        assert "videoSegments" in d
        assert len(d["videoSegments"]) == 1
        assert d["videoSegments"][0]["startMs"] == 0
        assert d["videoSegments"][0]["endMs"] == 5000

    def test_json_roundtrip_video_segments(self) -> None:
        seg1 = VideoSegment.create(start_ms=0, end_ms=2500)
        seg2 = VideoSegment.create(start_ms=2500, end_ms=5000, speed=2.0)
        session = RecordingSession(
            id="vs2", start_time=0, duration=5000,
            mouse_track=[MousePosition(0, 0, 0)],
            keyframes=[],
            video_segments=[seg1, seg2],
        )
        s2 = RecordingSession.from_json(session.to_json())
        assert s2.video_segments is not None
        assert len(s2.video_segments) == 2
        assert s2.video_segments[0].end_ms == 2500
        assert s2.video_segments[1].start_ms == 2500
        assert s2.video_segments[1].speed == 2.0

    def test_json_omits_video_segments_when_empty(self) -> None:
        session = RecordingSession(
            id="vs3", start_time=0, duration=100,
            mouse_track=[MousePosition(0, 0, 0)],
            keyframes=[],
        )
        d = json.loads(session.to_json())
        assert "videoSegments" not in d

    def test_backward_compat_no_video_segments(self) -> None:
        """Old projects without videoSegments should load fine."""
        session = RecordingSession(
            id="old", start_time=0, duration=100,
            mouse_track=[MousePosition(0, 0, 0)],
            keyframes=[],
        )
        s2 = RecordingSession.from_json(session.to_json())
        assert s2.video_segments is None


# ── Backward compatibility — missing required fields ────────────────


class TestFromDictErrorMessages:
    """Verify that missing required fields produce ValueError, not KeyError."""

    def test_mouse_position_missing_field(self) -> None:
        with pytest.raises(ValueError, match="MousePosition missing required field"):
            MousePosition.from_dict({"x": 1})

    def test_click_event_missing_field(self) -> None:
        with pytest.raises(ValueError, match="ClickEvent missing required field"):
            ClickEvent.from_dict({"x": 1, "y": 2})

    def test_video_segment_missing_field(self) -> None:
        with pytest.raises(ValueError, match="VideoSegment missing required field"):
            VideoSegment.from_dict({"id": "abc"})

    def test_voiceover_segment_missing_field(self) -> None:
        with pytest.raises(ValueError, match="VoiceoverSegment missing required field"):
            VoiceoverSegment.from_dict({"id": "abc"})

    def test_session_missing_required_field(self) -> None:
        """Old project missing 'duration' should produce a clear error."""
        minimal = json.dumps({"id": "old", "startTime": 0, "mouseTrack": []})
        with pytest.raises(ValueError, match="missing required field"):
            RecordingSession.from_json(minimal)


class TestMinimalOldProjectLoad:
    """Simulate loading a very old .fcproj with only essential fields."""

    def test_minimal_session_loads(self) -> None:
        minimal = json.dumps({
            "id": "old-v1",
            "startTime": 0,
            "duration": 3000,
            "mouseTrack": [{"x": 0, "y": 0, "timestamp": 0}],
        })
        s = RecordingSession.from_json(minimal)
        assert s.id == "old-v1"
        assert s.keyframes == []
        assert s.key_events is None
        assert s.click_events is None
        assert s.voiceover_segments is None
        assert s.video_segments is None
        assert s.trim_start_ms == 0.0
        assert s.trim_end_ms == 0.0


class TestConstants:
    def test_default_fps_and_interval_are_consistent(self) -> None:
        """Mouse polling interval should approximate 1000/FPS."""
        assert DEFAULT_FPS == 60
        assert DEFAULT_MOUSE_INTERVAL == 16
        # 16ms polling → 62.5 Hz, close to 60 fps target
        polling_hz = 1000.0 / DEFAULT_MOUSE_INTERVAL
        assert abs(polling_hz - DEFAULT_FPS) < 5, (
            f"Polling rate {polling_hz:.1f} Hz does not approximate FPS {DEFAULT_FPS}"
        )


# ── Chapter roundtrip ─────────────────────────────────────────────


class TestChapterRoundtrip:
    def test_roundtrip(self) -> None:
        """to_dict → from_dict preserves all fields."""
        ch = Chapter(timestamp_ms=12345, name="Intro", auto_detected=True)
        d = ch.to_dict()
        ch2 = Chapter.from_dict(d)
        assert ch2.timestamp_ms == ch.timestamp_ms
        assert ch2.name == ch.name
        assert ch2.auto_detected == ch.auto_detected

    def test_defaults_roundtrip(self) -> None:
        ch = Chapter(timestamp_ms=0, name="")
        d = ch.to_dict()
        ch2 = Chapter.from_dict(d)
        assert ch2.timestamp_ms == 0
        assert ch2.name == ""
        assert ch2.auto_detected is True  # default is True (heuristic-generated)


class TestRecordingSessionChaptersRoundtrip:
    def test_json_roundtrip_chapters(self) -> None:
        """RecordingSession with chapters survives to_json → from_json."""
        chapters = [
            Chapter(timestamp_ms=0, name="Intro", auto_detected=False),
            Chapter(timestamp_ms=5000, name="Demo", auto_detected=True),
        ]
        session = RecordingSession(
            id="ch-rt", start_time=0, duration=10000,
            mouse_track=[MousePosition(0, 0, 0)],
            keyframes=[],
            chapters=chapters,
        )
        s2 = RecordingSession.from_json(session.to_json())
        assert s2.chapters is not None
        assert len(s2.chapters) == 2
        assert s2.chapters[0].name == "Intro"
        assert s2.chapters[0].auto_detected is False
        assert s2.chapters[1].timestamp_ms == 5000
        assert s2.chapters[1].auto_detected is True


# ── ClickEffectPreset roundtrip ─────────────────────────────────


class TestClickEffectPresetRoundtrip:
    def test_roundtrip(self) -> None:
        """to_dict → from_dict preserves all fields."""
        preset = ClickEffectPreset(
            name="Purple", color=(138, 92, 246, 200), style="ripple",
            duration_ms=500, radius=30,
        )
        d = preset.to_dict()
        preset2 = ClickEffectPreset.from_dict(d)
        assert preset2.name == preset.name
        assert tuple(preset2.color) == tuple(preset.color)
        assert preset2.style == preset.style
        assert preset2.duration_ms == preset.duration_ms
        assert preset2.radius == preset.radius


# ── KeystrokeOverlayConfig roundtrip ──────────────────────────────


class TestKeystrokeOverlayConfigRoundtrip:
    def test_roundtrip(self) -> None:
        """to_dict → from_dict preserves all fields."""
        config = KeystrokeOverlayConfig(
            enabled=True,
            position="bottom-left",
            style="key-cap",
            display_duration_ms=2000,
            filter_mode="all",
            font_size=24,
            opacity=0.5,
        )
        d = config.to_dict()
        config2 = KeystrokeOverlayConfig.from_dict(d)
        assert config2.enabled == config.enabled
        assert config2.position == config.position
        assert config2.style == config.style
        assert config2.display_duration_ms == config.display_duration_ms
        assert config2.filter_mode == config.filter_mode
        assert config2.font_size == config.font_size
        assert config2.opacity == config.opacity

    def test_defaults_roundtrip(self) -> None:
        config = KeystrokeOverlayConfig()
        d = config.to_dict()
        config2 = KeystrokeOverlayConfig.from_dict(d)
        assert config2.enabled == config.enabled
        assert config2.filter_mode == "shortcuts-only"

    def test_filter_mode_validation(self) -> None:
        """from_dict with unrecognized filter_mode falls back to default."""
        d = KeystrokeOverlayConfig().to_dict()
        d["filterMode"] = "invalid-mode"
        config = KeystrokeOverlayConfig.from_dict(d)
        assert config.filter_mode == "shortcuts-only"


# ── Annotation roundtrips ────────────────────────────────────────


class TestTextAnnotationRoundtrip:
    def test_roundtrip(self) -> None:
        annot = TextAnnotation(
            id="t1", start_ms=100.0, end_ms=2000.0,
            x=0.3, y=0.7, text="Hello",
            font_size=24, color=(255, 0, 0, 128),
            background_color=(0, 0, 0, 180),
        )
        d = annot.to_dict()
        annot2 = TextAnnotation.from_dict(d)
        assert annot2.id == annot.id
        assert annot2.start_ms == annot.start_ms
        assert annot2.end_ms == annot.end_ms
        assert annot2.x == annot.x
        assert annot2.y == annot.y
        assert annot2.text == annot.text
        assert annot2.font_size == annot.font_size
        assert tuple(annot2.color) == tuple(annot.color)
        assert tuple(annot2.background_color) == tuple(annot.background_color)


class TestArrowAnnotationRoundtrip:
    def test_roundtrip(self) -> None:
        annot = ArrowAnnotation(
            id="a1", start_ms=500.0, end_ms=3000.0,
            x1=0.1, y1=0.2, x2=0.8, y2=0.9,
            color=(0, 255, 0, 255), thickness=5, head_size=20,
        )
        d = annot.to_dict()
        annot2 = ArrowAnnotation.from_dict(d)
        assert annot2.id == annot.id
        assert annot2.x1 == annot.x1
        assert annot2.y1 == annot.y1
        assert annot2.x2 == annot.x2
        assert annot2.y2 == annot.y2
        assert tuple(annot2.color) == tuple(annot.color)
        assert annot2.thickness == annot.thickness
        assert annot2.head_size == annot.head_size


class TestHighlightBoxRoundtrip:
    def test_roundtrip(self) -> None:
        annot = HighlightBox(
            id="h1", start_ms=0.0, end_ms=5000.0,
            x=0.2, y=0.3, width=0.4, height=0.2,
            color=(255, 204, 0, 100), opacity=0.6, border_width=3,
        )
        d = annot.to_dict()
        annot2 = HighlightBox.from_dict(d)
        assert annot2.id == annot.id
        assert annot2.x == annot.x
        assert annot2.y == annot.y
        assert annot2.width == annot.width
        assert annot2.height == annot.height
        assert tuple(annot2.color) == tuple(annot.color)
        assert annot2.opacity == annot.opacity
        assert annot2.border_width == annot.border_width


class TestAnnotationCollectionRoundtrip:
    def test_roundtrip(self) -> None:
        coll = AnnotationCollection(
            texts=[TextAnnotation(id="t1", start_ms=0, end_ms=1000, x=0.5, y=0.5, text="Hi")],
            arrows=[ArrowAnnotation(id="a1", start_ms=0, end_ms=1000, x1=0, y1=0, x2=1, y2=1)],
            highlights=[HighlightBox(id="h1", start_ms=0, end_ms=1000, x=0.1, y=0.1, width=0.5, height=0.5)],
        )
        d = coll.to_dict()
        coll2 = AnnotationCollection.from_dict(d)
        assert len(coll2.texts) == 1
        assert coll2.texts[0].id == "t1"
        assert len(coll2.arrows) == 1
        assert coll2.arrows[0].id == "a1"
        assert len(coll2.highlights) == 1
        assert coll2.highlights[0].id == "h1"

    def test_empty_roundtrip(self) -> None:
        coll = AnnotationCollection()
        d = coll.to_dict()
        coll2 = AnnotationCollection.from_dict(d)
        assert coll2.texts is None
        assert coll2.arrows is None
        assert coll2.highlights is None


# ── KeyEvent.vk_code roundtrip ─────────────────────────────────


class TestKeyEventVkCode:
    def test_vk_code_roundtrip(self) -> None:
        """vk_code survives to_dict → from_dict."""
        ke = KeyEvent(timestamp=100.0, x=10.0, y=20.0, vk_code=65)
        d = ke.to_dict()
        assert d["vkCode"] == 65
        ke2 = KeyEvent.from_dict(d)
        assert ke2.vk_code == 65

    def test_vk_code_none_omitted(self) -> None:
        """vk_code=None should not appear in serialized dict."""
        ke = KeyEvent(timestamp=100.0)
        d = ke.to_dict()
        assert "vkCode" not in d
        ke2 = KeyEvent.from_dict(d)
        assert ke2.vk_code is None
