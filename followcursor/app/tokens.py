"""Fluent 2 design tokens for FollowCursor.

Centralized design constants aligned with Windows 11 / Fluent 2.
All spacing uses a 4px base grid.  Corner radii use 4px (controls) / 8px
(containers).  Colors follow Fluent 2 neutral palette (grey ramp) and
semantic color roles.  Elevation system uses Fluent 2 shadow spec.

Reference:
- https://fluent2.microsoft.design/color
- https://fluent2.microsoft.design/color-tokens/
- https://fluent2.microsoft.design/elevation
"""

# ── Spacing (4 px base grid) ───────────────────────────────────────────
SPACE_XXS: int = 4
SPACE_XS: int = 8
SPACE_SM: int = 12
SPACE_MD: int = 16
SPACE_LG: int = 24
SPACE_XL: int = 32
SPACE_XXL: int = 48

# ── Corner radius ──────────────────────────────────────────────────────
RADIUS_SMALL: int = 4   # buttons, inputs, small controls
RADIUS_MEDIUM: int = 8  # dialogs, panels, containers, cards

# ── Fluent 2 Neutral Color Ramp (Dark Theme) ───────────────────────────
# Based on official Fluent 2 grey palette for dark mode
# Mapping: colorNeutralBackground* → BG_*, colorNeutralForeground* → FG_*
# grey[N] references from Fluent 2 global tokens

# Background layers (darkest → lightest)
# Aligned with Fluent 2 colorNeutralBackground hierarchy
BG_SOLID: str = "#000000"            # grey[0] / black — deepest base (canvas, root)
BG_LAYER_1: str = "#141414"          # grey[4] — app background, base layer
BG_LAYER_2: str = "#1f1f1f"          # grey[8] — panels, secondary surfaces
BG_LAYER_3: str = "#292929"          # grey[12] — raised cards, content areas
BG_LAYER_4: str = "#333333"          # grey[16] — elevated surfaces, tooltips
BG_LAYER_5: str = "#3d3d3d"          # grey[20] — highest background (dialogs, overlays)

# Interactive surface states
BG_SUBTLE: str = "transparent"       # colorSubtleBackground rest (hover: grey[22])
BG_SUBTLE_HOVER: str = "#383838"     # grey[22] — subtle hover (list items, etc.)
BG_SUBTLE_PRESSED: str = "#2e2e2e"   # grey[18] — subtle pressed
BG_SUBTLE_SELECTED: str = "#333333"  # grey[20] — subtle selected

# Card surfaces (from colorNeutralCardBackground)
BG_CARD: str = "#333333"             # grey[20] rest
BG_CARD_HOVER: str = "#3d3d3d"       # grey[24] hover
BG_CARD_PRESSED: str = "#2e2e2e"     # grey[18] pressed
BG_CARD_SELECTED: str = "#383838"    # grey[22] selected

# ── Fluent 2 Foreground (Text & Icons) ─────────────────────────────────
FG_1: str = "#ffffff"                # colorNeutralForeground1 — primary text (white in dark)
FG_2: str = "#d6d6d6"                # grey[84] — secondary text, labels
FG_3: str = "#adadad"                # grey[68] — tertiary text, placeholders
FG_4: str = "#999999"                # grey[60] — quaternary, disabled hints
FG_DISABLED: str = "#5c5c5c"         # grey[36] — disabled text
FG_INVERTED: str = "#242424"         # grey[14] — text on light/brand backgrounds

# ── Fluent 2 Borders / Strokes ─────────────────────────────────────────
STROKE_ACCESSIBLE: str = "#adadad"   # grey[68] — accessible borders (3:1 contrast)
STROKE_1: str = "#666666"            # grey[40] — default borders
STROKE_2: str = "#525252"            # grey[32] — dividers, secondary borders
STROKE_SUBTLE: str = "#0a0a0a"       # grey[4] — very subtle dividers

# ── Brand / Accent ─────────────────────────────────────────────────────
# FollowCursor brand color (purple) — kept from original design
# In Fluent 2 terms: colorBrandBackground / colorBrandForeground
BRAND: str = "#8b5cf6"                                # primary accent (rest)
BRAND_HOVER: str = "#9d74f7"                           # hover
BRAND_ACTIVE: str = "#7c3aed"                          # pressed / active
BRAND_TRANSLUCENT: str = "rgba(139, 92, 246, 0.18)"   # tinted surface (background2)
BRAND_TRANSLUCENT_HOVER: str = "rgba(139, 92, 246, 0.25)"
BRAND_TRANSLUCENT_STRONG: str = "rgba(139, 92, 246, 0.28)"
BRAND_DISABLED: str = "#4c3d7a"                        # disabled brand bg

# ── Fluent 2 Semantic Status Colors ───────────────────────────────────
# Success (green ramp) — colorStatusSuccess*
SUCCESS: str = "#10b981"             # green primary (Fluent 2 spec)
SUCCESS_BG_1: str = "#0c5239"        # green shade40 — success background
SUCCESS_BG_2: str = "#0f6b4a"        # green shade30 — success content bg
SUCCESS_FG: str = "#6ee7b7"          # green tint30 — success foreground on dark

# Danger (cranberry/red ramp) — colorStatusDanger*
DANGER: str = "#ef4444"              # cranberry primary (Fluent 2 spec)
DANGER_HOVER: str = "#f87171"        # tint variation
DANGER_DARK: str = "#dc2626"         # record button background (shade10)
DANGER_BG_1: str = "#5c1010"         # cranberry shade40 — danger background
DANGER_BG_2: str = "#7a1818"         # cranberry shade30 — danger content bg
DANGER_FG: str = "#fca5a5"           # cranberry tint30 — danger foreground on dark
DANGER_TRANSLUCENT: str = "rgba(239, 68, 68, 0.12)"
DANGER_TRANSLUCENT_STRONG: str = "rgba(239, 68, 68, 0.15)"

# Warning (orange ramp) — colorStatusWarning*
WARNING: str = "#f59e0b"             # orange primary (Fluent 2 spec)
WARNING_HOVER: str = "#fbbf24"       # tint variation
WARNING_BG_1: str = "#5c3a10"        # orange shade40 — warning background
WARNING_BG_2: str = "#7a4d18"        # orange shade30 — warning content bg
WARNING_FG: str = "#fed7aa"          # orange tint30 — warning foreground on dark

# Info (blue ramp) — colorStatusInfo* (using generic blue palette)
INFO: str = "#3b82f6"                # blue primary
INFO_HOVER: str = "#60a5fa"          # blue tint
INFO_BG_1: str = "#18395c"           # blue shade40 — info background
INFO_BG_2: str = "#204d7a"           # blue shade30 — info content bg
INFO_FG: str = "#93c5fd"             # blue tint30 — info foreground on dark

# ── Special surfaces ──────────────────────────────────────────────────
CLOSE_HOVER_BG: str = "#c42b1c"       # Windows-standard close-button red
DISCARD_BG: str = "#474747"           # grey[28] — discard button base
DISCARD_HOVER_BG: str = "#525252"     # grey[32] — discard hover
DIALOG_BG: str = "#1f1f1f"            # grey[8] — modal dialog backdrop
OVERLAY_BG: str = "rgba(31, 31, 31, 0.92)"  # semi-transparent panel bg (grey[8] + alpha)

# ── Typography ─────────────────────────────────────────────────────────
FONT_FAMILY: str = '"Segoe UI Variable", "Segoe UI", sans-serif'
FONT_FAMILY_MONO: str = '"Segoe UI Variable", "Segoe UI", monospace'
FONT_SIZE_CAPTION: int = 11   # captions, small labels, status text
FONT_SIZE_BODY: int = 13      # default body text
FONT_SIZE_SUBTITLE: int = 15  # sub-headings
FONT_SIZE_TITLE: int = 16     # section titles, record button
FONT_SIZE_HEADER: int = 20    # page headers

# ── Animation (durations in milliseconds) ──────────────────────────────
DURATION_FAST: int = 100       # state transitions – hover, press
DURATION_NORMAL: int = 200     # panel transitions
DURATION_SLOW: int = 300       # content reveals, overlays

# ── Fluent 2 Elevation / Shadow System ─────────────────────────────────
# Based on official Fluent 2 elevation spec (dark theme)
# Reference: https://fluent2.microsoft.design/elevation
# Fluent shadows combine key + ambient shadows for depth perception

# Shadow Layer 0 — No elevation (flat surfaces)
SHADOW_LAYER_0_BLUR: int = 0
SHADOW_LAYER_0_OFFSET_Y: int = 0
SHADOW_LAYER_0_KEY: str = "rgba(0, 0, 0, 0)"
SHADOW_LAYER_0_AMBIENT: str = "rgba(0, 0, 0, 0)"

# Shadow Layer 1 (Shadow2) — Minimal depth (buttons at rest, subtle cards)
SHADOW_LAYER_1_BLUR: int = 2
SHADOW_LAYER_1_OFFSET_Y: int = 1
SHADOW_LAYER_1_KEY: str = "rgba(0, 0, 0, 0.28)"        # dark theme: 28% key
SHADOW_LAYER_1_AMBIENT: str = "rgba(0, 0, 0, 0.24)"    # dark theme: 24% ambient

# Shadow Layer 2 (Shadow4) — Cards, list items
SHADOW_LAYER_2_BLUR: int = 4
SHADOW_LAYER_2_OFFSET_Y: int = 2
SHADOW_LAYER_2_KEY: str = "rgba(0, 0, 0, 0.28)"
# NOTE: Qt's QGraphicsDropShadowEffect only supports a single shadow. The ambient
# shadow tokens below are defined for Fluent 2 spec reference but are not used.
# Future custom renderers (QPainter compositing, WebView overlays) may use both.
SHADOW_LAYER_2_AMBIENT: str = "rgba(0, 0, 0, 0.24)"

# Shadow Layer 3 (Shadow8) — Command bars, tooltips, dropdowns
SHADOW_LAYER_3_BLUR: int = 8
SHADOW_LAYER_3_OFFSET_Y: int = 4
SHADOW_LAYER_3_KEY: str = "rgba(0, 0, 0, 0.28)"
SHADOW_LAYER_3_AMBIENT: str = "rgba(0, 0, 0, 0.24)"  # unused (see SHADOW_LAYER_2_AMBIENT note)

# Shadow Layer 4 (Shadow16) — Dialogs, callouts, flyouts
SHADOW_LAYER_4_BLUR: int = 16
SHADOW_LAYER_4_OFFSET_Y: int = 8
SHADOW_LAYER_4_KEY: str = "rgba(0, 0, 0, 0.28)"
SHADOW_LAYER_4_AMBIENT: str = "rgba(0, 0, 0, 0.24)"  # unused (see SHADOW_LAYER_2_AMBIENT note)

# Material effects — subtle transparency for overlays (acrylic-inspired)
MATERIAL_OVERLAY_ALPHA: float = 0.92  # backdrop opacity
MATERIAL_CARD_ALPHA: float = 0.98     # card/dialog opacity

# ── Focus ring ─────────────────────────────────────────────────────────
FOCUS_RING_WIDTH: int = 2
FOCUS_RING_OFFSET: int = 2

# ── Scrollbar ──────────────────────────────────────────────────────────
SCROLLBAR_THIN: int = 6         # default narrow width
SCROLLBAR_WIDE: int = 12        # expanded width on hover
SCROLLBAR_MIN_HEIGHT: int = 24  # minimum handle length

# ── Legacy compatibility aliases ───────────────────────────────────────
# Keep backward compat with existing QSS selectors during transition
BG_CANVAS = BG_LAYER_1          # maps to grey[4]
BG_PANEL = BG_LAYER_2           # maps to grey[8]
BG_SURFACE = BG_LAYER_3         # maps to grey[12]
BG_ELEVATED = BG_LAYER_4        # maps to grey[16]
BG_INTERACTIVE = BG_LAYER_4     # maps to grey[16] (interactive defaults to elevated)
BG_HOVER = BG_CARD_HOVER        # maps to grey[24]
BG_HOVER_STRONG = "#474747"     # grey[28] for strong emphasis

BORDER_SUBTLE = STROKE_SUBTLE   # maps to grey[4]
BORDER_MEDIUM = STROKE_2        # maps to grey[32]
BORDER_STRONG = STROKE_1        # maps to grey[40]

FG_PRIMARY = FG_1               # white
FG_SECONDARY = FG_2             # grey[84]
FG_MUTED = FG_3                 # grey[68]
FG_DIM = FG_4                   # grey[60]
FG_WHITE = FG_1                 # white

CARD_BG = BG_CARD               # grey[20]
CARD_BORDER = STROKE_1          # grey[40]
CARD_HOVER_BG = BG_CARD_HOVER   # grey[24]

DANGER_LIGHT = DANGER_FG        # cranberry tint30
DANGER_TEXT = DANGER            # cranberry primary

# Legacy shadow tokens (map to Fluent 2 Layer 2 and 3)
SHADOW_SUBTLE_BLUR = SHADOW_LAYER_2_BLUR
SHADOW_SUBTLE_OFFSET = SHADOW_LAYER_2_OFFSET_Y
SHADOW_SUBTLE_COLOR = SHADOW_LAYER_2_KEY
SHADOW_MEDIUM_BLUR = SHADOW_LAYER_3_BLUR
SHADOW_MEDIUM_OFFSET = SHADOW_LAYER_3_OFFSET_Y
SHADOW_MEDIUM_COLOR = SHADOW_LAYER_3_KEY
