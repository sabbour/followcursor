"""Background presets for video composition.

Each preset defines the background behind the device bezel.
Supports solid, gradient, and pattern backgrounds.
Gradient sub-types: linear, radial (centre glow), spotlight (corner glow).
Pattern sub-types: wavy.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class BackgroundPreset:
    """A named background preset."""
    name: str
    kind: str  # "solid", "gradient", "radial", "spotlight", "wavy"
    # Colors as (R, G, B) tuples (0-255)
    color_top: Tuple[int, int, int]
    color_bottom: Tuple[int, int, int]  # same as top for solid
    category: str = ""  # "solid", "gradient", or "pattern" — set automatically

    def __post_init__(self) -> None:
        if not self.category:
            if self.kind == "solid":
                self.category = "solid"
            elif self.kind in ("gradient", "radial", "spotlight"):
                self.category = "gradient"
            else:
                self.category = "pattern"

    @property
    def is_gradient(self) -> bool:
        return self.kind == "gradient"

    @property
    def is_wavy(self) -> bool:
        return self.kind == "wavy"

    @property
    def is_pattern(self) -> bool:
        return self.category == "pattern"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "color_top": list(self.color_top),
            "color_bottom": list(self.color_bottom),
        }

    @staticmethod
    def from_dict(d: dict) -> "BackgroundPreset":
        return BackgroundPreset(
            name=d["name"],
            kind=d["kind"],
            color_top=tuple(d["color_top"]),
            color_bottom=tuple(d["color_bottom"]),
        )


# ── Wave-layer definitions (shared by compositor & exporter) ────────

#: Each tuple: (y_center_frac, amplitude_frac, frequency, phase, alpha, use_top_color)
WAVE_LAYERS = [
    (0.18, 0.08, 1.5, 0.0,  0.30, True),
    (0.35, 0.06, 2.3, 1.5,  0.20, False),
    (0.52, 0.10, 1.0, 3.0,  0.35, True),
    (0.68, 0.05, 3.0, 0.7,  0.18, False),
    (0.82, 0.07, 1.8, 4.2,  0.25, True),
]

# ── Category constants ──────────────────────────────────────────────
CAT_SOLID   = "solid"
CAT_GRADIENT = "gradient"
CAT_PATTERN  = "pattern"
CATEGORIES = [CAT_SOLID, CAT_GRADIENT, CAT_PATTERN]
CATEGORY_LABELS = {CAT_SOLID: "Solid", CAT_GRADIENT: "Gradient", CAT_PATTERN: "Pattern"}

# ── Built-in presets ────────────────────────────────────────────────

PRESETS: List[BackgroundPreset] = [
    # ── Solids (39 — every colour from the palette) ─────────────────
    # Row 1: Light tones
    BackgroundPreset("Pure White",       "solid", (255, 255, 255), (255, 255, 255)),
    BackgroundPreset("Warm Light Gray",  "solid", (232, 230, 223), (232, 230, 223)),
    BackgroundPreset("Light Gray",       "solid", (217, 217, 214), (217, 217, 214)),
    BackgroundPreset("Light Brown",      "solid", (225, 211, 199), (225, 211, 199)),
    BackgroundPreset("Light Yellow",     "solid", (255, 227, 153), (255, 227, 153)),
    BackgroundPreset("Light Orange",     "solid", (255, 163, 139), (255, 163, 139)),
    BackgroundPreset("Light Red",        "solid", (255, 179, 187), (255, 179, 187)),
    BackgroundPreset("Light Magenta",    "solid", (213, 158, 215), (213, 158, 215)),
    BackgroundPreset("Light Purple",     "solid", (197, 180, 227), (197, 180, 227)),
    BackgroundPreset("Light Blue",       "solid", (141, 200, 232), (141, 200, 232)),
    BackgroundPreset("Light Teal",       "solid", (185, 220, 210), (185, 220, 210)),
    BackgroundPreset("Light Green",      "solid", (212, 236, 142), (212, 236, 142)),
    BackgroundPreset("Blue Black",       "solid", (9, 31, 44),     (9, 31, 44)),
    # Row 2: Mid tones
    BackgroundPreset("Off White",        "solid", (244, 243, 245), (244, 243, 245)),
    BackgroundPreset("Mid Gray",         "solid", (215, 210, 203), (215, 210, 203)),
    BackgroundPreset("Cool Gray",        "solid", (177, 179, 179), (177, 179, 179)),
    BackgroundPreset("Brown",            "solid", (191, 148, 116), (191, 148, 116)),
    BackgroundPreset("Yellow",           "solid", (255, 185, 0),   (255, 185, 0)),
    BackgroundPreset("Orange",           "solid", (255, 92, 57),   (255, 92, 57)),
    BackgroundPreset("Red",              "solid", (244, 54, 76),   (244, 54, 76)),
    BackgroundPreset("Magenta",          "solid", (192, 59, 196),  (192, 59, 196)),
    BackgroundPreset("Purple",           "solid", (134, 97, 197),  (134, 97, 197)),
    BackgroundPreset("Blue",             "solid", (0, 120, 212),   (0, 120, 212)),
    BackgroundPreset("Teal",             "solid", (73, 197, 177),  (73, 197, 177)),
    BackgroundPreset("Green",            "solid", (141, 233, 113), (141, 233, 113)),
    BackgroundPreset("Pure Black",       "solid", (0, 0, 0),       (0, 0, 0)),
    # Row 3: Dark tones
    BackgroundPreset("Warm White",       "solid", (255, 248, 243), (255, 248, 243)),
    BackgroundPreset("Warm Gray",        "solid", (140, 130, 121), (140, 130, 121)),
    BackgroundPreset("Dark Gray",        "solid", (69, 65, 66),    (69, 65, 66)),
    BackgroundPreset("Dark Brown",       "solid", (92, 71, 56),    (92, 71, 56)),
    BackgroundPreset("Dark Yellow",      "solid", (127, 90, 26),   (127, 90, 26)),
    BackgroundPreset("Dark Orange",      "solid", (115, 57, 29),   (115, 57, 29)),
    BackgroundPreset("Dark Red",         "solid", (115, 38, 47),   (115, 38, 47)),
    BackgroundPreset("Dark Magenta",     "solid", (112, 37, 115),  (112, 37, 115)),
    BackgroundPreset("Dark Purple",      "solid", (70, 54, 104),   (70, 54, 104)),
    BackgroundPreset("Dark Blue",        "solid", (42, 68, 111),   (42, 68, 111)),
    BackgroundPreset("Dark Teal",        "solid", (34, 91, 98),    (34, 91, 98)),
    BackgroundPreset("Dark Green",       "solid", (7, 100, 29),    (7, 100, 29)),
    BackgroundPreset("Brown Black",      "solid", (41, 24, 23),    (41, 24, 23)),

    # ── Gradients — Light → Dark ───────────────────────────────────
    BackgroundPreset("Warm Gray Gradient",  "gradient", (232, 230, 223), (140, 130, 121)),
    BackgroundPreset("Cool Gray Gradient",  "gradient", (217, 217, 214), (69, 65, 66)),
    BackgroundPreset("Brown Gradient",      "gradient", (225, 211, 199), (92, 71, 56)),
    BackgroundPreset("Yellow Gradient",     "gradient", (255, 227, 153), (127, 90, 26)),
    BackgroundPreset("Orange Gradient",     "gradient", (255, 163, 139), (115, 57, 29)),
    BackgroundPreset("Red Gradient",        "gradient", (255, 179, 187), (115, 38, 47)),
    BackgroundPreset("Magenta Gradient",    "gradient", (213, 158, 215), (112, 37, 115)),
    BackgroundPreset("Purple Gradient",     "gradient", (197, 180, 227), (70, 54, 104)),
    BackgroundPreset("Blue Gradient",       "gradient", (141, 200, 232), (42, 68, 111)),
    BackgroundPreset("Teal Gradient",       "gradient", (185, 220, 210), (34, 91, 98)),
    BackgroundPreset("Green Gradient",      "gradient", (212, 236, 142), (7, 100, 29)),
    # Mid → Dark
    BackgroundPreset("Brown Deep",    "gradient", (191, 148, 116), (92, 71, 56)),
    BackgroundPreset("Yellow Deep",   "gradient", (255, 185, 0),   (127, 90, 26)),
    BackgroundPreset("Orange Deep",   "gradient", (255, 92, 57),   (115, 57, 29)),
    BackgroundPreset("Red Deep",      "gradient", (244, 54, 76),   (115, 38, 47)),
    BackgroundPreset("Magenta Deep",  "gradient", (192, 59, 196),  (112, 37, 115)),
    BackgroundPreset("Purple Deep",   "gradient", (134, 97, 197),  (70, 54, 104)),
    BackgroundPreset("Blue Deep",     "gradient", (0, 120, 212),   (42, 68, 111)),
    BackgroundPreset("Teal Deep",     "gradient", (73, 197, 177),  (34, 91, 98)),
    BackgroundPreset("Green Deep",    "gradient", (141, 233, 113), (7, 100, 29)),

    # ── Gradients — Radial (centre glow) ────────────────────────────
    BackgroundPreset("Blue Radial",    "radial", (0, 120, 212),   (9, 31, 44)),
    BackgroundPreset("Purple Radial",  "radial", (134, 97, 197),  (41, 24, 23)),
    BackgroundPreset("Teal Radial",    "radial", (73, 197, 177),  (9, 31, 44)),
    BackgroundPreset("Orange Radial",  "radial", (255, 92, 57),   (41, 24, 23)),
    BackgroundPreset("Green Radial",   "radial", (141, 233, 113), (9, 31, 44)),
    BackgroundPreset("Magenta Radial", "radial", (192, 59, 196),  (9, 31, 44)),
    BackgroundPreset("Red Radial",     "radial", (244, 54, 76),   (41, 24, 23)),
    BackgroundPreset("Yellow Radial",  "radial", (255, 185, 0),   (41, 24, 23)),
    BackgroundPreset("Warm Radial",    "radial", (232, 230, 223), (69, 65, 66)),
    BackgroundPreset("Gray Radial",    "radial", (177, 179, 179), (9, 31, 44)),
    BackgroundPreset("Brown Radial",   "radial", (191, 148, 116), (41, 24, 23)),

    # ── Gradients — Spotlight (corner glow) ────────────────────────
    BackgroundPreset("Blue Spotlight",    "spotlight", (0, 120, 212),   (9, 31, 44)),
    BackgroundPreset("Purple Spotlight",  "spotlight", (134, 97, 197),  (41, 24, 23)),
    BackgroundPreset("Teal Spotlight",    "spotlight", (73, 197, 177),  (9, 31, 44)),
    BackgroundPreset("Orange Spotlight",  "spotlight", (255, 92, 57),   (41, 24, 23)),
    BackgroundPreset("Green Spotlight",   "spotlight", (141, 233, 113), (9, 31, 44)),
    BackgroundPreset("Warm Spotlight",    "spotlight", (255, 227, 153), (69, 65, 66)),

    # ── Patterns — Wavy ────────────────────────────────────────────
    BackgroundPreset("Ocean Waves",    "wavy", (0, 120, 212),     (42, 68, 111)),
    BackgroundPreset("Sunset Waves",   "wavy", (255, 92, 57),     (115, 38, 47)),
    BackgroundPreset("Aurora Waves",   "wavy", (73, 197, 177),    (70, 54, 104)),
    BackgroundPreset("Lavender Waves", "wavy", (213, 158, 215),   (70, 54, 104)),
    BackgroundPreset("Forest Waves",   "wavy", (141, 233, 113),   (34, 91, 98)),
    BackgroundPreset("Ember Waves",    "wavy", (255, 185, 0),     (115, 57, 29)),
    BackgroundPreset("Midnight Waves", "wavy", (42, 68, 111),     (9, 31, 44)),
    BackgroundPreset("Coral Waves",    "wavy", (244, 54, 76),     (112, 37, 115)),
]

DEFAULT_PRESET = PRESETS[0]  # "Pure White"

# Convenience accessors by category
SOLID_PRESETS   = [p for p in PRESETS if p.category == CAT_SOLID]
GRADIENT_PRESETS = [p for p in PRESETS if p.category == CAT_GRADIENT]
PATTERN_PRESETS  = [p for p in PRESETS if p.category == CAT_PATTERN]
