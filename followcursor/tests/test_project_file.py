"""Tests for app.project_file — save / load .fcproj bundles."""

import json
import os
import tempfile
import zipfile

import pytest

from app.project_file import save_project, load_project, PROJ_EXT, _JSON_NAME, _VIDEO_NAME
from app.models import (
    MousePosition,
    KeyEvent,
    ClickEvent,
    ZoomKeyframe,
    RecordingSession,
)
from app.backgrounds import BackgroundPreset
from app.frames import FramePreset, DEFAULT_FRAME


# ── Helpers ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def dummy_video(tmp_path) -> str:
    """Create a small dummy AVI file for testing."""
    path = str(tmp_path / "test_recording.avi")
    with open(path, "wb") as f:
        f.write(b"\x00" * 256)  # minimal placeholder
    return path


@pytest.fixture
def full_session() -> RecordingSession:
    return RecordingSession(
        id="proj-test-001",
        start_time=0.0,
        duration=5000.0,
        mouse_track=[
            MousePosition(x=100, y=200, timestamp=0),
            MousePosition(x=110, y=210, timestamp=16),
            MousePosition(x=120, y=220, timestamp=32),
        ],
        keyframes=[
            ZoomKeyframe.create(timestamp=1000, zoom=1.5, x=0.3, y=0.4, duration=600),
            ZoomKeyframe.create(timestamp=3000, zoom=1.0, x=0.5, y=0.5, duration=1200),
        ],
        key_events=[KeyEvent(timestamp=500)],
        click_events=[ClickEvent(x=105, y=205, timestamp=600)],
        frame_timestamps=[0, 16, 32],
        trim_start_ms=100,
        trim_end_ms=4500,
    )


@pytest.fixture
def sample_bg() -> BackgroundPreset:
    return BackgroundPreset("Test BG", "gradient", (255, 0, 0), (0, 0, 255))


# ── save_project ────────────────────────────────────────────────────


class TestSaveProject:
    def test_creates_zip(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "test"), dummy_video, full_session)
        assert out.endswith(PROJ_EXT)
        assert os.path.isfile(out)
        assert zipfile.is_zipfile(out)

    def test_appends_extension(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "noext"), dummy_video, full_session)
        assert out.endswith(PROJ_EXT)

    def test_does_not_double_extension(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "already.fcproj"), dummy_video, full_session)
        assert out.endswith(PROJ_EXT)
        assert not out.endswith(PROJ_EXT + PROJ_EXT)

    def test_zip_contains_json_and_video(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "test"), dummy_video, full_session)
        with zipfile.ZipFile(out, "r") as zf:
            names = zf.namelist()
            assert _JSON_NAME in names
            assert _VIDEO_NAME in names

    def test_json_content_valid(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "test"), dummy_video, full_session)
        with zipfile.ZipFile(out, "r") as zf:
            data = json.loads(zf.read(_JSON_NAME))
        assert data["id"] == "proj-test-001"
        assert data["duration"] == 5000.0
        assert len(data["mouseTrack"]) == 3
        assert len(data["keyframes"]) == 2

    def test_includes_monitor_rect(self, tmp_dir, dummy_video, full_session) -> None:
        mon = {"left": 0, "top": 0, "width": 1920, "height": 1080}
        out = save_project(str(tmp_dir / "test"), dummy_video, full_session,
                           monitor_rect=mon)
        with zipfile.ZipFile(out, "r") as zf:
            data = json.loads(zf.read(_JSON_NAME))
        assert data["monitorRect"] == mon

    def test_includes_actual_fps(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "test"), dummy_video, full_session,
                           actual_fps=59.94)
        with zipfile.ZipFile(out, "r") as zf:
            data = json.loads(zf.read(_JSON_NAME))
        assert data["actualFps"] == 59.94

    def test_includes_bg_preset(self, tmp_dir, dummy_video, full_session, sample_bg) -> None:
        out = save_project(str(tmp_dir / "test"), dummy_video, full_session,
                           bg_preset=sample_bg)
        with zipfile.ZipFile(out, "r") as zf:
            data = json.loads(zf.read(_JSON_NAME))
        assert data["bgPreset"]["name"] == "Test BG"

    def test_includes_frame_preset(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "test"), dummy_video, full_session,
                           frame_preset=DEFAULT_FRAME)
        with zipfile.ZipFile(out, "r") as zf:
            data = json.loads(zf.read(_JSON_NAME))
        assert data["framePreset"]["name"] == "Wide Bezel"

    def test_missing_video(self, tmp_dir, full_session) -> None:
        """Should still create the ZIP without the AVI if the video is missing."""
        out = save_project(str(tmp_dir / "test"), "/nonexistent.avi", full_session)
        with zipfile.ZipFile(out, "r") as zf:
            names = zf.namelist()
            assert _JSON_NAME in names
            assert _VIDEO_NAME not in names


# ── load_project ────────────────────────────────────────────────────


class TestLoadProject:
    def test_roundtrip(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "rt"), dummy_video, full_session,
                           monitor_rect={"left": 0, "top": 0, "width": 1920, "height": 1080},
                           actual_fps=60.0)
        result = load_project(out)

        assert result["session"].id == full_session.id
        assert result["session"].duration == full_session.duration
        assert len(result["session"].mouse_track) == len(full_session.mouse_track)
        assert len(result["session"].keyframes) == len(full_session.keyframes)
        assert result["monitor_rect"]["width"] == 1920
        assert result["actual_fps"] == 60.0

    def test_roundtrip_with_presets(self, tmp_dir, dummy_video, full_session, sample_bg) -> None:
        out = save_project(str(tmp_dir / "rt"), dummy_video, full_session,
                           bg_preset=sample_bg, frame_preset=DEFAULT_FRAME)
        result = load_project(out)
        assert result["bg_preset"].name == "Test BG"
        assert result["frame_preset"].name == "Wide Bezel"

    def test_video_extracted(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "rt"), dummy_video, full_session)
        result = load_project(out)
        assert result["video_path"] != ""
        assert os.path.isfile(result["video_path"])

    def test_trim_preserved(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "rt"), dummy_video, full_session)
        result = load_project(out)
        assert result["session"].trim_start_ms == 100
        assert result["session"].trim_end_ms == 4500

    def test_key_events_preserved(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "rt"), dummy_video, full_session)
        result = load_project(out)
        assert len(result["session"].key_events) == 1

    def test_click_events_preserved(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "rt"), dummy_video, full_session)
        result = load_project(out)
        assert len(result["session"].click_events) == 1

    def test_invalid_file_raises(self, tmp_dir) -> None:
        bad = str(tmp_dir / "bad.fcproj")
        with open(bad, "w") as f:
            f.write("not a zip")
        with pytest.raises(ValueError, match="Not a valid"):
            load_project(bad)

    def test_missing_json_raises(self, tmp_dir) -> None:
        """ZIP without project.json should raise ValueError."""
        bad = str(tmp_dir / "nojson.fcproj")
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("random.txt", "hello")
        with pytest.raises(ValueError, match="missing"):
            load_project(bad)

    def test_missing_video_returns_empty_path(self, tmp_dir, full_session) -> None:
        """If the video was not included, video_path should be empty."""
        out = save_project(str(tmp_dir / "novid"), "/nonexistent.avi", full_session)
        result = load_project(out)
        assert result["video_path"] == ""

    def test_missing_bg_preset_returns_none(self, tmp_dir, dummy_video, full_session) -> None:
        """If no bg preset was saved, load should return None."""
        out = save_project(str(tmp_dir / "nobg"), dummy_video, full_session)
        result = load_project(out)
        assert result["bg_preset"] is None

    def test_missing_frame_preset_returns_none(self, tmp_dir, dummy_video, full_session) -> None:
        out = save_project(str(tmp_dir / "nofr"), dummy_video, full_session)
        result = load_project(out)
        assert result["frame_preset"] is None
