"""Device frame presets for video composition.

Each preset defines the device bezel style drawn around the video.
Includes "No Frame" for a clean borderless look.
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class FramePreset:
    """A named device-frame style."""
    name: str
    bezel_width: float        # px at reference width (900px device)
    outer_radius: float       # corner radius of outer shell
    inner_radius: float       # corner radius of screen opening
    bezel_color: Tuple[int, int, int]      # RGB
    edge_color: Tuple[int, int, int]       # RGB outer rim
    edge_width: float         # multiplier for edge stroke
    show_camera: bool         # draw camera dot
    shadow_layers: int        # 0 = no shadow
    padding: float            # fraction of canvas (0.0 = edge-to-edge)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "bezel_width": self.bezel_width,
            "outer_radius": self.outer_radius,
            "inner_radius": self.inner_radius,
            "bezel_color": list(self.bezel_color),
            "edge_color": list(self.edge_color),
            "edge_width": self.edge_width,
            "show_camera": self.show_camera,
            "shadow_layers": self.shadow_layers,
            "padding": self.padding,
        }

    @staticmethod
    def from_dict(d: dict) -> "FramePreset":
        return FramePreset(
            name=d["name"],
            bezel_width=d["bezel_width"],
            outer_radius=d["outer_radius"],
            inner_radius=d["inner_radius"],
            bezel_color=tuple(d["bezel_color"]),
            edge_color=tuple(d["edge_color"]),
            edge_width=d["edge_width"],
            show_camera=d["show_camera"],
            shadow_layers=d["shadow_layers"],
            padding=d["padding"],
        )

    @property
    def is_none(self) -> bool:
        return self.bezel_width <= 0 and self.shadow_layers <= 0


# ── Built-in presets ────────────────────────────────────────────────

FRAME_PRESETS: List[FramePreset] = [
    FramePreset(
        name="Wide Bezel",
        bezel_width=28.0, outer_radius=18.0, inner_radius=6.0,
        bezel_color=(26, 26, 26), edge_color=(107, 107, 107),
        edge_width=1.5, show_camera=True, shadow_layers=4, padding=0.04,
    ),
    FramePreset(
        name="Slim Bezel",
        bezel_width=18.0, outer_radius=14.0, inner_radius=6.0,
        bezel_color=(30, 30, 30), edge_color=(80, 80, 80),
        edge_width=1.0, show_camera=True, shadow_layers=4, padding=0.04,
    ),
    FramePreset(
        name="Thin Border",
        bezel_width=6.0, outer_radius=10.0, inner_radius=6.0,
        bezel_color=(20, 20, 20), edge_color=(60, 60, 60),
        edge_width=1.0, show_camera=False, shadow_layers=3, padding=0.03,
    ),
    FramePreset(
        name="Shadow Only",
        bezel_width=0.0, outer_radius=12.0, inner_radius=12.0,
        bezel_color=(0, 0, 0), edge_color=(0, 0, 0),
        edge_width=0.0, show_camera=False, shadow_layers=4, padding=0.04,
    ),
    FramePreset(
        name="No Frame",
        bezel_width=0.0, outer_radius=0.0, inner_radius=0.0,
        bezel_color=(0, 0, 0), edge_color=(0, 0, 0),
        edge_width=0.0, show_camera=False, shadow_layers=0, padding=0.0,
    ),
]

DEFAULT_FRAME = FRAME_PRESETS[0]  # "Wide Bezel"
