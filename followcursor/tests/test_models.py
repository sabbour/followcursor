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

    def test_dict_keys(self) -> None:
        d = KeyEvent(timestamp=0).to_dict()
        assert set(d.keys()) == {"timestamp"}


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


# ── Constants ───────────────────────────────────────────────────────


class TestConstants:
    def test_default_fps(self) -> None:
        assert DEFAULT_FPS == 60

    def test_default_mouse_interval(self) -> None:
        assert DEFAULT_MOUSE_INTERVAL == 16
