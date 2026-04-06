"""Core data models for FollowCursor.

Defines the dataclasses used throughout the application for recording
sessions, input events, and zoom keyframes.  All models support
JSON serialization via ``to_dict()`` / ``from_dict()`` (or ``to_json()``
/ ``from_json()`` for top-level sessions).
"""

from dataclasses import dataclass
from typing import List
import uuid
import json


@dataclass
class MousePosition:
    """A single cursor position sample captured during recording.

    Coordinates are in **physical screen pixels** (not DPI-scaled).
    """
    x: float
    y: float
    timestamp: float  # ms since recording start

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        return {"x": self.x, "y": self.y, "timestamp": self.timestamp}

    @staticmethod
    def from_dict(d: dict) -> "MousePosition":
        """Reconstruct from a dict produced by ``to_dict()``."""
        try:
            return MousePosition(x=d["x"], y=d["y"], timestamp=d["timestamp"])
        except KeyError as exc:
            raise ValueError(f"MousePosition missing required field: {exc}") from exc


@dataclass
class KeyEvent:
    """A single keystroke timestamp with optional cursor position.

    Coordinates are in **physical screen pixels** (not DPI-scaled).
    Position is captured via ``GetCursorPos`` at keystroke time and
    indicates *where* the user is typing.
    """
    timestamp: float  # ms since recording start
    x: float | None = None  # cursor x at keystroke time (physical px)
    y: float | None = None  # cursor y at keystroke time (physical px)

    def to_dict(self) -> dict:
        d: dict = {"timestamp": self.timestamp}
        if self.x is not None:
            d["x"] = self.x
        if self.y is not None:
            d["y"] = self.y
        return d

    @staticmethod
    def from_dict(d: dict) -> "KeyEvent":
        return KeyEvent(
            timestamp=d["timestamp"],
            x=d.get("x"),
            y=d.get("y"),
        )


@dataclass
class ClickEvent:
    """A mouse click with position and timestamp."""
    x: float
    y: float
    timestamp: float  # ms since recording start

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "timestamp": self.timestamp}

    @staticmethod
    def from_dict(d: dict) -> "ClickEvent":
        try:
            return ClickEvent(x=d["x"], y=d["y"], timestamp=d["timestamp"])
        except KeyError as exc:
            raise ValueError(f"ClickEvent missing required field: {exc}") from exc


@dataclass
class ZoomKeyframe:
    """A single zoom/pan keyframe used by the zoom engine.

    Keyframes come in pairs: a zoom-in (``zoom > 1``) and a matching
    zoom-out (``zoom = 1``).  The engine interpolates between
    consecutive keyframes using quintic ease-out easing.
    """

    id: str
    timestamp: float  # ms
    zoom: float
    x: float  # 0-1 normalized pan
    y: float
    duration: float  # ms for transition
    reason: str = ""  # human-readable reason (e.g. "Mouse activity burst")
    speed: float = 1.0  # playback speed multiplier (0.5–10.0, stored on zoom-in kf)

    @staticmethod
    def create(
        timestamp: float,
        zoom: float,
        x: float = 0.5,
        y: float = 0.5,
        duration: float = 600.0,
        reason: str = "",
        speed: float = 1.0,
    ) -> "ZoomKeyframe":
        """Factory that auto-generates a UUID for the keyframe."""
        return ZoomKeyframe(
            id=str(uuid.uuid4()),
            timestamp=timestamp,
            zoom=zoom,
            x=x,
            y=y,
            duration=duration,
            reason=reason,
            speed=speed,
        )

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        d = {
            "id": self.id,
            "timestamp": self.timestamp,
            "zoom": self.zoom,
            "x": self.x,
            "y": self.y,
            "duration": self.duration,
        }
        if self.reason:
            d["reason"] = self.reason
        if self.speed != 1.0:
            d["speed"] = self.speed
        return d

    @staticmethod
    def from_dict(d: dict) -> "ZoomKeyframe":
        """Reconstruct from a dict, ignoring unknown keys for forward compat."""
        # Filter to only known fields to avoid TypeError from extra keys
        known = {"id", "timestamp", "zoom", "x", "y", "duration", "reason", "speed"}
        filtered = {k: v for k, v in d.items() if k in known}
        # Validate speed to prevent division-by-zero and hangs on
        # malformed/corrupt project files.
        raw_speed = filtered.get("speed", 1.0)
        try:
            speed = float(raw_speed)
        except (TypeError, ValueError):
            speed = 1.0
        if speed <= 0.0:
            speed = 1.0
        elif speed > 10.0:
            speed = 10.0
        filtered["speed"] = speed
        return ZoomKeyframe(**filtered)


@dataclass
class VideoSegment:
    """A contiguous section of the recording timeline.

    A recording starts as one segment spanning the full duration.
    Splitting at the playhead subdivides it into two adjacent segments.
    Each segment can later be independently deleted or speed-adjusted.
    """

    id: str
    start_ms: float  # inclusive start time (ms since recording start)
    end_ms: float    # exclusive end time (ms)
    speed: float = 1.0  # playback speed multiplier (1.0 = normal)

    @staticmethod
    def create(
        start_ms: float,
        end_ms: float,
        speed: float = 1.0,
    ) -> "VideoSegment":
        """Factory that auto-generates a UUID."""
        return VideoSegment(
            id=str(uuid.uuid4()),
            start_ms=start_ms,
            end_ms=end_ms,
            speed=speed,
        )

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "startMs": self.start_ms,
            "endMs": self.end_ms,
        }
        if self.speed != 1.0:
            d["speed"] = self.speed
        return d

    @staticmethod
    def from_dict(d: dict) -> "VideoSegment":
        try:
            raw_speed = d.get("speed", 1.0)
            try:
                speed = float(raw_speed)
            except (TypeError, ValueError):
                speed = 1.0
            if speed <= 0.0:
                speed = 0.1  # minimum non-zero speed to prevent division-by-zero in duration calculations
            elif speed > 10.0:
                speed = 10.0
            return VideoSegment(
                id=d["id"],
                start_ms=d["startMs"],
                end_ms=d["endMs"],
                speed=speed,
            )
        except KeyError as exc:
            raise ValueError(f"VideoSegment missing required field: {exc}") from exc


@dataclass
class RecordingSession:
    """Top-level container for everything captured in one recording.

    Includes mouse track, key/click events, zoom keyframes, trim
    points, and per-frame timestamps.  Serialized to/from JSON for
    ``.fcproj`` project files.
    """

    id: str
    start_time: float
    duration: float
    mouse_track: List[MousePosition]
    keyframes: List[ZoomKeyframe]
    key_events: List[KeyEvent] | None = None
    click_events: List[ClickEvent] | None = None
    frame_timestamps: List[float] | None = None
    trim_start_ms: float = 0.0
    trim_end_ms: float = 0.0  # 0 = no trim (use full duration)
    voiceover_segments: List["VoiceoverSegment"] | None = None
    video_segments: List["VideoSegment"] | None = None

    def to_json(self) -> str:
        """Serialize the entire session to a JSON string."""
        data = {
            "id": self.id,
            "startTime": self.start_time,
            "duration": self.duration,
            "mouseTrack": [m.to_dict() for m in self.mouse_track],
            "keyframes": [k.to_dict() for k in self.keyframes],
        }
        if self.key_events:
            data["keyEvents"] = [k.to_dict() for k in self.key_events]
        if self.click_events:
            data["clickEvents"] = [c.to_dict() for c in self.click_events]
        if self.frame_timestamps:
            data["frameTimestamps"] = self.frame_timestamps
        if self.trim_start_ms > 0:
            data["trimStartMs"] = self.trim_start_ms
        if self.trim_end_ms > 0:
            data["trimEndMs"] = self.trim_end_ms
        if self.voiceover_segments:
            data["voiceoverSegments"] = [v.to_dict() for v in self.voiceover_segments]
        if self.video_segments:
            data["videoSegments"] = [vs.to_dict() for vs in self.video_segments]
        return json.dumps(data, indent=2)

    @staticmethod
    def from_json(s: str) -> "RecordingSession":
        """Reconstruct a full session from its JSON representation.

        Tolerates missing optional fields for backward compatibility with
        older .fcproj versions.  Required fields (``id``, ``startTime``,
        ``duration``, ``mouseTrack``) raise ``ValueError`` with a clear
        message instead of raw ``KeyError``.  ``keyframes`` is optional and
        defaults to an empty list when absent for backward compatibility.
        """
        d = json.loads(s)
        try:
            session_id = d["id"]
            start_time = d["startTime"]
            duration = d["duration"]
            mouse_track = [MousePosition.from_dict(m) for m in d["mouseTrack"]]
            keyframes = [ZoomKeyframe.from_dict(k) for k in d.get("keyframes", [])]
        except KeyError as exc:
            raise ValueError(
                f"Project file missing required field: {exc}"
            ) from exc

        key_events = None
        if "keyEvents" in d:
            key_events = [KeyEvent.from_dict(k) for k in d["keyEvents"]]
        click_events = None
        if "clickEvents" in d:
            click_events = [ClickEvent.from_dict(c) for c in d["clickEvents"]]
        frame_timestamps = d.get("frameTimestamps")
        voiceover_segments = None
        if "voiceoverSegments" in d:
            voiceover_segments = [VoiceoverSegment.from_dict(v) for v in d["voiceoverSegments"]]
        video_segments = None
        if "videoSegments" in d:
            video_segments = [VideoSegment.from_dict(vs) for vs in d["videoSegments"]]
        return RecordingSession(
            id=session_id,
            start_time=start_time,
            duration=duration,
            mouse_track=mouse_track,
            keyframes=keyframes,
            key_events=key_events,
            click_events=click_events,
            frame_timestamps=frame_timestamps,
            trim_start_ms=d.get("trimStartMs", 0.0),
            trim_end_ms=d.get("trimEndMs", 0.0),
            voiceover_segments=voiceover_segments,
            video_segments=video_segments,
        )


@dataclass
class VoiceoverSegment:
    """A single voiceover segment with text, position, and audio.

    Users create these at specific timeline positions.  TTS synthesis
    converts the text to speech and stores the audio file path.
    """

    id: str
    timestamp: float  # ms — start position on the timeline
    text: str  # user-authored voiceover text
    voice: str = "en-US-Ava:DragonHDLatestNeural"  # TTS voice name
    audio_path: str = ""  # path to synthesized audio file (empty = not yet synthesized)
    duration_ms: float = 0.0  # audio duration in ms (0 = unknown/not synthesized)
    rate: float = 1.0  # speech rate multiplier (0.0–3.0, 1.0 = normal)
    volume: float = 1.0  # volume multiplier (0.0–3.0, 1.0 = normal)

    @staticmethod
    def create(
        timestamp: float,
        text: str,
        voice: str = "en-US-Ava:DragonHDLatestNeural",
        rate: float = 1.0,
        volume: float = 1.0,
    ) -> "VoiceoverSegment":
        """Factory that auto-generates a UUID."""
        return VoiceoverSegment(
            id=str(uuid.uuid4()),
            timestamp=timestamp,
            text=text,
            voice=voice,
            rate=rate,
            volume=volume,
        )

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "timestamp": self.timestamp,
            "text": self.text,
            "voice": self.voice,
        }
        if self.duration_ms > 0:
            d["durationMs"] = self.duration_ms
        if self.rate != 1.0:
            d["rate"] = self.rate
        if self.volume != 1.0:
            d["volume"] = self.volume
        return d

    @staticmethod
    def from_dict(d: dict) -> "VoiceoverSegment":
        try:
            # Validate rate and volume bounds
            raw_rate = d.get("rate", 1.0)
            try:
                rate = float(raw_rate)
            except (TypeError, ValueError):
                rate = 1.0
            rate = max(0.0, min(3.0, rate))

            raw_volume = d.get("volume", 1.0)
            try:
                volume = float(raw_volume)
            except (TypeError, ValueError):
                volume = 1.0
            volume = max(0.0, min(3.0, volume))

            return VoiceoverSegment(
                id=d["id"],
                timestamp=d["timestamp"],
                text=d["text"],
                voice=d.get("voice", "en-US-Ava:DragonHDLatestNeural"),
                duration_ms=d.get("durationMs", 0.0),
                rate=rate,
                volume=volume,
            )
        except KeyError as exc:
            raise ValueError(f"VoiceoverSegment missing required field: {exc}") from exc


DEFAULT_FPS = 60
DEFAULT_MOUSE_INTERVAL = 16
