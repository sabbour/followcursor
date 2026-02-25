from dataclasses import dataclass
from typing import List
import uuid
import json


@dataclass
class MousePosition:
    x: float
    y: float
    timestamp: float  # ms since recording start

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "timestamp": self.timestamp}

    @staticmethod
    def from_dict(d: dict) -> "MousePosition":
        return MousePosition(x=d["x"], y=d["y"], timestamp=d["timestamp"])


@dataclass
class KeyEvent:
    """A single keystroke timestamp (no key identity stored for privacy)."""
    timestamp: float  # ms since recording start

    def to_dict(self) -> dict:
        return {"timestamp": self.timestamp}

    @staticmethod
    def from_dict(d: dict) -> "KeyEvent":
        return KeyEvent(timestamp=d["timestamp"])


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
        return ClickEvent(x=d["x"], y=d["y"], timestamp=d["timestamp"])


@dataclass
class ZoomKeyframe:
    id: str
    timestamp: float  # ms
    zoom: float
    x: float  # 0-1 normalized pan
    y: float
    duration: float  # ms for transition
    reason: str = ""  # human-readable reason (e.g. "Mouse activity burst")

    @staticmethod
    def create(
        timestamp: float,
        zoom: float,
        x: float = 0.5,
        y: float = 0.5,
        duration: float = 600.0,
        reason: str = "",
    ) -> "ZoomKeyframe":
        return ZoomKeyframe(
            id=str(uuid.uuid4()),
            timestamp=timestamp,
            zoom=zoom,
            x=x,
            y=y,
            duration=duration,
            reason=reason,
        )

    def to_dict(self) -> dict:
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
        return d

    @staticmethod
    def from_dict(d: dict) -> "ZoomKeyframe":
        # Filter to only known fields to avoid TypeError from extra keys
        known = {"id", "timestamp", "zoom", "x", "y", "duration", "reason"}
        filtered = {k: v for k, v in d.items() if k in known}
        return ZoomKeyframe(**filtered)


@dataclass
class RecordingSession:
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

    def to_json(self) -> str:
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
        return json.dumps(data, indent=2)

    @staticmethod
    def from_json(s: str) -> "RecordingSession":
        d = json.loads(s)
        key_events = None
        if "keyEvents" in d:
            key_events = [KeyEvent.from_dict(k) for k in d["keyEvents"]]
        click_events = None
        if "clickEvents" in d:
            click_events = [ClickEvent.from_dict(c) for c in d["clickEvents"]]
        frame_timestamps = d.get("frameTimestamps")
        return RecordingSession(
            id=d["id"],
            start_time=d["startTime"],
            duration=d["duration"],
            mouse_track=[MousePosition.from_dict(m) for m in d["mouseTrack"]],
            keyframes=[ZoomKeyframe.from_dict(k) for k in d["keyframes"]],
            key_events=key_events,
            click_events=click_events,
            frame_timestamps=frame_timestamps,
            trim_start_ms=d.get("trimStartMs", 0.0),
            trim_end_ms=d.get("trimEndMs", 0.0),
        )


DEFAULT_FPS = 60
DEFAULT_MOUSE_INTERVAL = 16
