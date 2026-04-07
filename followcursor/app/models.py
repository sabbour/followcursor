"""Core data models for FollowCursor.

Defines the dataclasses used throughout the application for recording
sessions, input events, and zoom keyframes.  All models support
JSON serialization via ``to_dict()`` / ``from_dict()`` (or ``to_json()``
/ ``from_json()`` for top-level sessions).
"""

import logging
from dataclasses import dataclass
from typing import List
import uuid
import json

logger = logging.getLogger(__name__)

# Allowed values for KeystrokeOverlayConfig.filter_mode
VALID_FILTER_MODES = frozenset({"all", "modifiers-only", "shortcuts-only"})


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
    vk_code: int | None = None  # Windows virtual key code

    def to_dict(self) -> dict:
        d: dict = {"timestamp": self.timestamp}
        if self.x is not None:
            d["x"] = self.x
        if self.y is not None:
            d["y"] = self.y
        if self.vk_code is not None:
            d["vkCode"] = self.vk_code
        return d

    @staticmethod
    def from_dict(d: dict) -> "KeyEvent":
        return KeyEvent(
            timestamp=d["timestamp"],
            x=d.get("x"),
            y=d.get("y"),
            vk_code=d.get("vkCode", d.get("vk_code")),
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
class Chapter:
    """A chapter marker for navigation within a recording.

    Chapters help users navigate long recordings by marking scene boundaries.
    They can be auto-detected based on activity patterns or manually created.
    """

    timestamp_ms: int  # start time of this chapter
    name: str  # display name (e.g., "Chapter 1", "Scene 2", or custom name)
    auto_detected: bool = True  # True if heuristic-generated, False if manual

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        return {
            "timestampMs": self.timestamp_ms,
            "name": self.name,
            "autoDetected": self.auto_detected,
        }

    @staticmethod
    def from_dict(d: dict) -> "Chapter":
        """Reconstruct from a dict produced by ``to_dict()``."""
        try:
            return Chapter(
                timestamp_ms=int(d["timestampMs"]),
                name=d["name"],
                auto_detected=d.get("autoDetected", True),
            )
        except KeyError as exc:
            raise ValueError(f"Chapter missing required field: {exc}") from exc


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
    chapters: List["Chapter"] | None = None

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
        if self.chapters:
            data["chapters"] = [c.to_dict() for c in self.chapters]
        return json.dumps(data, indent=2)

    @staticmethod
    def from_json(s: str) -> "RecordingSession":
        """Reconstruct a full session from its JSON representation.

        Tolerates missing optional fields for backward compatibility with
        older .fcproj versions.  Required fields (``id``, ``startTime``,
        ``duration``, ``mouseTrack``) raise ``ValueError`` with a clear
        message instead of raw ``KeyError``.  ``keyframes`` is optional
        (defaults to an empty list when absent) for backward compatibility.
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
        chapters = None
        if "chapters" in d:
            chapters = [Chapter.from_dict(c) for c in d["chapters"]]
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
            chapters=chapters,
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


@dataclass
class ClickEffectPreset:
    """A click effect style preset with color, style, duration, and radius.

    Defines the visual appearance of click ripple effects in preview and export.
    """

    name: str
    color: tuple[int, int, int, int]  # RGBA (0-255)
    style: str  # "ripple" | "burst" | "highlight"
    duration_ms: int
    radius: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "color": list(self.color),
            "style": self.style,
            "durationMs": self.duration_ms,
            "radius": self.radius,
        }

    @staticmethod
    def from_dict(d: dict) -> "ClickEffectPreset":
        try:
            raw_color = list(d["color"])
            # Coerce to 4 RGBA ints clamped to 0-255
            while len(raw_color) < 4:
                raw_color.append(255)
            color = tuple(max(0, min(255, int(c))) for c in raw_color[:4])
            return ClickEffectPreset(
                name=d["name"],
                color=color,
                style=d.get("style", "ripple"),
                duration_ms=d.get("durationMs", 400),
                radius=d.get("radius", 24),
            )
        except KeyError as exc:
            raise ValueError(f"ClickEffectPreset missing required field: {exc}") from exc


# ── Built-in click effect presets ───────────────────────────────────

CLICK_EFFECT_PRESETS = [
    ClickEffectPreset("Subtle Purple", (138, 92, 246, 220), "ripple", 400, 24),
    ClickEffectPreset("Bold Red", (239, 68, 68, 240), "ripple", 350, 28),
    ClickEffectPreset("Neon Cyan", (34, 211, 238, 230), "ripple", 450, 26),
    ClickEffectPreset("Minimal Gray", (156, 163, 175, 180), "ripple", 300, 20),
    ClickEffectPreset("High Contrast Yellow", (250, 204, 21, 250), "ripple", 380, 30),
    ClickEffectPreset("Clean White", (255, 255, 255, 200), "ripple", 350, 22),
    ClickEffectPreset("Soft Green", (74, 222, 128, 210), "ripple", 400, 24),
    ClickEffectPreset("Invisible", (0, 0, 0, 0), "ripple", 0, 0),
]

DEFAULT_CLICK_EFFECT = CLICK_EFFECT_PRESETS[0]  # Subtle Purple


@dataclass
class KeystrokeOverlayConfig:
    """Configuration for keystroke visualization overlay.

    Controls how keystrokes are rendered during video export and preview.
    """
    enabled: bool = False
    position: str = "bottom-center"  # "bottom-center", "bottom-left", "near-cursor"
    style: str = "floating-badge"    # "floating-badge", "minimal-text", "key-cap"
    display_duration_ms: int = 1500  # how long keystrokes remain visible
    filter_mode: str = "shortcuts-only"  # "all", "modifiers-only", "shortcuts-only"
    font_size: int = 18
    opacity: float = 0.85            # 0.0 - 1.0

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        return {
            "enabled": self.enabled,
            "position": self.position,
            "style": self.style,
            "displayDurationMs": self.display_duration_ms,
            "filterMode": self.filter_mode,
            "fontSize": self.font_size,
            "opacity": self.opacity,
        }

    @staticmethod
    def from_dict(d: dict) -> "KeystrokeOverlayConfig":
        """Reconstruct from a dict produced by ``to_dict()``."""
        raw_mode = d.get("filterMode", "shortcuts-only")
        if raw_mode not in VALID_FILTER_MODES:
            logger.warning(
                "Unknown keystroke filter_mode %r, defaulting to 'shortcuts-only'",
                raw_mode,
            )
            raw_mode = "shortcuts-only"
        return KeystrokeOverlayConfig(
            enabled=d.get("enabled", False),
            position=d.get("position", "bottom-center"),
            style=d.get("style", "floating-badge"),
            display_duration_ms=d.get("displayDurationMs", 1500),
            filter_mode=raw_mode,
            font_size=d.get("fontSize", 18),
            opacity=d.get("opacity", 0.85),
        )


@dataclass
class TextAnnotation:
    """A text annotation displayed for a time range.
    
    Text annotations overlay the video with user-defined text at a specific
    position for a given time range.
    """
    id: str
    start_ms: float
    end_ms: float
    x: float  # 0-1 normalized position
    y: float  # 0-1 normalized position
    text: str
    font_size: int = 18
    color: tuple[int, int, int, int] = (255, 255, 255, 255)  # RGBA
    background_color: tuple[int, int, int, int] | None = (30, 30, 30, 200)  # RGBA or None for no background
    
    @staticmethod
    def create(
        start_ms: float,
        end_ms: float,
        x: float = 0.5,
        y: float = 0.5,
        text: str = "Text",
        font_size: int = 18,
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        background_color: tuple[int, int, int, int] | None = (30, 30, 30, 200),
    ) -> "TextAnnotation":
        """Factory that auto-generates a UUID."""
        return TextAnnotation(
            id=str(uuid.uuid4()),
            start_ms=start_ms,
            end_ms=end_ms,
            x=x,
            y=y,
            text=text,
            font_size=font_size,
            color=color,
            background_color=background_color,
        )
    
    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        d = {
            "id": self.id,
            "startMs": self.start_ms,
            "endMs": self.end_ms,
            "x": self.x,
            "y": self.y,
            "text": self.text,
            "fontSize": self.font_size,
            "color": list(self.color),
        }
        if self.background_color is not None:
            d["backgroundColor"] = list(self.background_color)
        return d
    
    @staticmethod
    def from_dict(d: dict) -> "TextAnnotation":
        """Reconstruct from a dict produced by ``to_dict()``."""
        try:
            bg_color = None
            if "backgroundColor" in d:
                bg_color = tuple(d["backgroundColor"])
            return TextAnnotation(
                id=d["id"],
                start_ms=d["startMs"],
                end_ms=d["endMs"],
                x=d["x"],
                y=d["y"],
                text=d["text"],
                font_size=d.get("fontSize", 18),
                color=tuple(d.get("color", [255, 255, 255, 255])),
                background_color=bg_color,
            )
        except KeyError as exc:
            raise ValueError(f"TextAnnotation missing required field: {exc}") from exc


@dataclass
class ArrowAnnotation:
    """An arrow annotation pointing from one location to another.
    
    Arrow annotations draw directional arrows to highlight movement or
    connections between UI elements.
    """
    id: str
    start_ms: float
    end_ms: float
    x1: float  # 0-1 normalized start position
    y1: float
    x2: float  # 0-1 normalized end position
    y2: float
    color: tuple[int, int, int, int] = (255, 204, 0, 255)  # RGBA (yellow)
    thickness: int = 3
    head_size: int = 12
    
    @staticmethod
    def create(
        start_ms: float,
        end_ms: float,
        x1: float = 0.3,
        y1: float = 0.3,
        x2: float = 0.5,
        y2: float = 0.5,
        color: tuple[int, int, int, int] = (255, 204, 0, 255),
        thickness: int = 3,
        head_size: int = 12,
    ) -> "ArrowAnnotation":
        """Factory that auto-generates a UUID."""
        return ArrowAnnotation(
            id=str(uuid.uuid4()),
            start_ms=start_ms,
            end_ms=end_ms,
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            color=color,
            thickness=thickness,
            head_size=head_size,
        )
    
    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        return {
            "id": self.id,
            "startMs": self.start_ms,
            "endMs": self.end_ms,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "color": list(self.color),
            "thickness": self.thickness,
            "headSize": self.head_size,
        }
    
    @staticmethod
    def from_dict(d: dict) -> "ArrowAnnotation":
        """Reconstruct from a dict produced by ``to_dict()``."""
        try:
            return ArrowAnnotation(
                id=d["id"],
                start_ms=d["startMs"],
                end_ms=d["endMs"],
                x1=d["x1"],
                y1=d["y1"],
                x2=d["x2"],
                y2=d["y2"],
                color=tuple(d.get("color", [255, 204, 0, 255])),
                thickness=d.get("thickness", 3),
                head_size=d.get("headSize", 12),
            )
        except KeyError as exc:
            raise ValueError(f"ArrowAnnotation missing required field: {exc}") from exc


@dataclass
class HighlightBox:
    """A highlight box annotation to emphasize a rectangular area.
    
    Highlight boxes draw semi-transparent rectangles to draw attention to
    specific UI elements or regions.
    """
    id: str
    start_ms: float
    end_ms: float
    x: float  # 0-1 normalized position
    y: float
    width: float  # 0-1 normalized size
    height: float
    color: tuple[int, int, int, int] = (255, 204, 0, 100)  # RGBA (yellow, semi-transparent)
    opacity: float = 0.4  # 0.0 - 1.0
    border_width: int = 2
    
    @staticmethod
    def create(
        start_ms: float,
        end_ms: float,
        x: float = 0.3,
        y: float = 0.3,
        width: float = 0.2,
        height: float = 0.15,
        color: tuple[int, int, int, int] = (255, 204, 0, 100),
        opacity: float = 0.4,
        border_width: int = 2,
    ) -> "HighlightBox":
        """Factory that auto-generates a UUID."""
        return HighlightBox(
            id=str(uuid.uuid4()),
            start_ms=start_ms,
            end_ms=end_ms,
            x=x,
            y=y,
            width=width,
            height=height,
            color=color,
            opacity=opacity,
            border_width=border_width,
        )
    
    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        return {
            "id": self.id,
            "startMs": self.start_ms,
            "endMs": self.end_ms,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "color": list(self.color),
            "opacity": self.opacity,
            "borderWidth": self.border_width,
        }
    
    @staticmethod
    def from_dict(d: dict) -> "HighlightBox":
        """Reconstruct from a dict produced by ``to_dict()``."""
        try:
            return HighlightBox(
                id=d["id"],
                start_ms=d["startMs"],
                end_ms=d["endMs"],
                x=d["x"],
                y=d["y"],
                width=d["width"],
                height=d["height"],
                color=tuple(d.get("color", [255, 204, 0, 100])),
                opacity=d.get("opacity", 0.4),
                border_width=d.get("borderWidth", 2),
            )
        except KeyError as exc:
            raise ValueError(f"HighlightBox missing required field: {exc}") from exc


@dataclass
class AnnotationCollection:
    """Container for all annotation types in a recording session.
    
    Groups text, arrow, and highlight annotations together for easy
    serialization and rendering.
    """
    texts: List[TextAnnotation] | None = None
    arrows: List[ArrowAnnotation] | None = None
    highlights: List[HighlightBox] | None = None
    
    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        d = {}
        if self.texts:
            d["texts"] = [t.to_dict() for t in self.texts]
        if self.arrows:
            d["arrows"] = [a.to_dict() for a in self.arrows]
        if self.highlights:
            d["highlights"] = [h.to_dict() for h in self.highlights]
        return d
    
    @staticmethod
    def from_dict(d: dict) -> "AnnotationCollection":
        """Reconstruct from a dict produced by ``to_dict()``."""
        texts = None
        if "texts" in d:
            texts = [TextAnnotation.from_dict(t) for t in d["texts"]]
        arrows = None
        if "arrows" in d:
            arrows = [ArrowAnnotation.from_dict(a) for a in d["arrows"]]
        highlights = None
        if "highlights" in d:
            highlights = [HighlightBox.from_dict(h) for h in d["highlights"]]
        return AnnotationCollection(texts=texts, arrows=arrows, highlights=highlights)


DEFAULT_FPS = 60
DEFAULT_MOUSE_INTERVAL = 16
