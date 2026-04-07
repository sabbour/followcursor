"""Fluent 2 design tokens for FollowCursor.

Centralized design constants aligned with Windows 11 / Fluent 2.
All spacing uses a 4px base grid.  Corner radii use 4px (controls) / 8px
(containers).  Colour values are taken from the existing dark theme palette
so that this first token pass is a *refactor*, not a redesign.
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

# ── Background layers (darkest → lightest) ─────────────────────────────
BG_CANVAS: str = "#0e0d19"       # deepest layer – control bar, preview area
BG_PANEL: str = "#131221"        # panels – title bar, sidebar, editor, timeline
BG_SURFACE: str = "#1b1a2e"      # general widget background
BG_ELEVATED: str = "#201f34"     # raised surfaces – cards, items, placeholder
BG_INTERACTIVE: str = "#28263e"  # clickable surfaces – buttons, tooltips
BG_HOVER: str = "#353350"        # hover state for interactive elements
BG_HOVER_STRONG: str = "#3f3d5c"  # stronger hover (active drag, emphasis)

# ── Border ─────────────────────────────────────────────────────────────
BORDER_SUBTLE: str = "#2d2b45"   # low-contrast dividers
BORDER_MEDIUM: str = "#3d3b55"   # default control borders
BORDER_STRONG: str = "#4e4c68"   # hover / focus borders

# ── Foreground ─────────────────────────────────────────────────────────
FG_PRIMARY: str = "#e4e4ed"      # main body text
FG_SECONDARY: str = "#8886a0"    # secondary labels, inactive controls
FG_MUTED: str = "#5a5873"        # subtle text, status labels
FG_DIM: str = "#5a5873"          # dimmest text (same as muted for now)
FG_WHITE: str = "#ffffff"        # pure white (logo, selected text)
FG_DISABLED: str = "#9898b0"     # disabled control text

# ── Brand / Accent ─────────────────────────────────────────────────────
BRAND: str = "#8b5cf6"                                # primary accent
BRAND_HOVER: str = "#9d74f7"                           # hover
BRAND_ACTIVE: str = "#a78bfa"                          # active / pressed
BRAND_TRANSLUCENT: str = "rgba(139, 92, 246, 0.18)"   # tinted surface
BRAND_TRANSLUCENT_HOVER: str = "rgba(139, 92, 246, 0.25)"
BRAND_TRANSLUCENT_STRONG: str = "rgba(139, 92, 246, 0.28)"
BRAND_DISABLED: str = "#4c3d7a"                        # disabled brand bg

# ── Status ─────────────────────────────────────────────────────────────
SUCCESS: str = "#22c55e"
SUCCESS_HOVER: str = "#4ade80"

DANGER: str = "#ef4444"
DANGER_HOVER: str = "#f87171"
DANGER_DARK: str = "#dc2626"          # record button background
DANGER_LIGHT: str = "#fca5a5"         # very light red accent
DANGER_TEXT: str = "#ef5350"          # danger text on dark backgrounds
DANGER_TRANSLUCENT: str = "rgba(239, 68, 68, 0.12)"
DANGER_TRANSLUCENT_STRONG: str = "rgba(239, 68, 68, 0.15)"

WARNING: str = "#f59e0b"
WARNING_HOVER: str = "#fbbf24"

INFO: str = "#3b82f6"
INFO_HOVER: str = "#60a5fa"

# ── Special surfaces ──────────────────────────────────────────────────
CLOSE_HOVER_BG: str = "#c42b1c"       # Windows-standard close-button red
DISCARD_BG: str = "#374151"
DISCARD_HOVER_BG: str = "#4b5563"
DIALOG_BG: str = "#141325"            # modal dialog backdrop
CARD_BG: str = "#1e1d33"              # source card surface
CARD_BORDER: str = "#3d3a58"          # source card border
CARD_HOVER_BG: str = "#2a2845"        # source card hover / selected
OVERLAY_BG: str = "rgba(19, 18, 33, 0.92)"  # semi-transparent panel bg

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

# ── Shadow ─────────────────────────────────────────────────────────────
SHADOW_SUBTLE_BLUR: int = 4
SHADOW_SUBTLE_OFFSET: int = 2
SHADOW_SUBTLE_COLOR: str = "rgba(0, 0, 0, 0.25)"
SHADOW_MEDIUM_BLUR: int = 8
SHADOW_MEDIUM_OFFSET: int = 4
SHADOW_MEDIUM_COLOR: str = "rgba(0, 0, 0, 0.35)"

# ── Focus ring ─────────────────────────────────────────────────────────
FOCUS_RING_WIDTH: int = 2
FOCUS_RING_OFFSET: int = 2

# ── Scrollbar ──────────────────────────────────────────────────────────
SCROLLBAR_THIN: int = 6         # default narrow width
SCROLLBAR_WIDE: int = 12        # expanded width on hover
SCROLLBAR_MIN_HEIGHT: int = 24  # minimum handle length
