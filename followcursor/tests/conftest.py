"""Shared pytest fixtures for FollowCursor tests."""

import pytest

from app.models import (
    MousePosition,
    KeyEvent,
    ClickEvent,
    ZoomKeyframe,
    RecordingSession,
)
from app.backgrounds import BackgroundPreset, PRESETS as BACKGROUND_PRESETS
from app.frames import FramePreset, FRAME_PRESETS, DEFAULT_FRAME


# ── Monitor rect ────────────────────────────────────────────────────

@pytest.fixture
def monitor_rect() -> dict:
    """A 1920×1080 monitor at origin."""
    return {"left": 0, "top": 0, "width": 1920, "height": 1080}


# ── Mouse track helpers ────────────────────────────────────────────

@pytest.fixture
def simple_mouse_track() -> list[MousePosition]:
    """Short straight-line mouse track (20 samples, 320ms)."""
    return [
        MousePosition(x=100.0 + i * 10, y=200.0, timestamp=i * 16.0)
        for i in range(20)
    ]


@pytest.fixture
def long_mouse_track() -> list[MousePosition]:
    """10-second mouse track with a fast→slow settlement at 5s."""
    track: list[MousePosition] = []
    for i in range(625):  # ~10s at 16ms intervals
        t = i * 16.0
        if t < 4000:
            # Slow drift
            x = 500.0 + i * 0.5
            y = 500.0
        elif t < 5000:
            # Fast move
            x = 500.0 + (t - 4000) * 1.0
            y = 500.0 + (t - 4000) * 0.5
        else:
            # Settle
            x = 1500.0
            y = 1000.0
        track.append(MousePosition(x=x, y=y, timestamp=t))
    return track


# ── Key / click event helpers ──────────────────────────────────────

@pytest.fixture
def typing_burst() -> list[KeyEvent]:
    """Rapid typing burst at ~3s (20 keys over 1s)."""
    return [KeyEvent(timestamp=3000.0 + i * 50) for i in range(20)]


@pytest.fixture
def click_cluster() -> list[ClickEvent]:
    """3 clicks near (960, 540) around 6s."""
    return [
        ClickEvent(x=950, y=530, timestamp=6000),
        ClickEvent(x=960, y=540, timestamp=6200),
        ClickEvent(x=970, y=550, timestamp=6400),
    ]


# ── Zoom keyframes ─────────────────────────────────────────────────

@pytest.fixture
def zoom_in_out_pair() -> list[ZoomKeyframe]:
    """A simple zoom-in / zoom-out keyframe pair."""
    return [
        ZoomKeyframe.create(timestamp=1000, zoom=1.5, x=0.3, y=0.4, duration=600, reason="Test zoom in"),
        ZoomKeyframe.create(timestamp=4000, zoom=1.0, x=0.5, y=0.5, duration=1200, reason="Test zoom out"),
    ]


# ── Recording session ──────────────────────────────────────────────

@pytest.fixture
def sample_session(simple_mouse_track: list[MousePosition]) -> RecordingSession:
    """Minimal recording session for serialization tests."""
    return RecordingSession(
        id="test-session-001",
        start_time=0.0,
        duration=320.0,
        mouse_track=simple_mouse_track,
        keyframes=[
            ZoomKeyframe.create(timestamp=100, zoom=1.5, x=0.3, y=0.4, duration=600),
        ],
        key_events=[KeyEvent(timestamp=50), KeyEvent(timestamp=150)],
        click_events=[ClickEvent(x=110, y=200, timestamp=80)],
        frame_timestamps=[i * 16.0 for i in range(20)],
        trim_start_ms=32.0,
        trim_end_ms=288.0,
    )


# ── Presets ─────────────────────────────────────────────────────────

@pytest.fixture
def sample_bg_preset() -> BackgroundPreset:
    return BACKGROUND_PRESETS[0]


@pytest.fixture
def sample_frame_preset() -> FramePreset:
    return DEFAULT_FRAME
