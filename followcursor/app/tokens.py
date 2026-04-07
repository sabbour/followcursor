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

# ── Spacing (Fluent 2 Spacer Tokens) ──────────────────────────────────
# Based on https://fluent2.microsoft.design/layout
# Uses 2px base unit with Fluent 2 spacer values (size20, size40, size80, etc.)
SPACE_NONE: int = 0   # sizeNone
SPACE_XXS: int = 2   # size20 — tight compact spacing
SPACE_XS: int = 4    # size40 — minimal padding
SPACE_SM: int = 8    # size80 — small controls, icons
SPACE_MD: int = 12   # size120 — default control padding
SPACE_LG: int = 16   # size160 — section spacing
SPACE_XL: int = 24   # size240 — panel spacing
SPACE_XXL: int = 32  # size320 — large gaps, hero sections
SPACE_XXXL: int = 48 # size480 — major layout divisions

# Additional Fluent 2 spacer tokens for fine control
SPACE_6: int = 6     # size60 — icon-text gap
SPACE_10: int = 10   # size100 — list item padding
SPACE_20: int = 20   # size200 — medium sections
SPACE_28: int = 28   # size280 — extended section gaps
SPACE_36: int = 36   # size360 — wide component spacing
SPACE_40: int = 40   # size400 — large containers
SPACE_52: int = 52   # size520 — extra-wide sections
SPACE_56: int = 56   # size560 — jumbo component gaps
SPACE_64: int = 64   # size640 — extra-large divisions

# ── Corner Radius (Fluent 2 Shapes) ───────────────────────────────────
# Based on https://fluent2.microsoft.design/shapes
# Global-Corner-Radius tokens
RADIUS_NONE: int = 0      # Navigation bars, tabs, edge-aligned elements
RADIUS_SMALL: int = 4     # Global-Corner-Radius-40 — buttons, inputs, small controls
RADIUS_MEDIUM: int = 8    # Global-Corner-Radius-80 — large buttons, cards
RADIUS_LARGE: int = 12    # Global-Corner-Radius-120 — sheets, popovers, large surfaces
RADIUS_XLARGE: int = 16   # Global-Corner-Radius-160 — extra-large containers
RADIUS_CIRCULAR: int = 9999  # Global-Corner-Radius-Circular — avatars, status dots (50% effective)

# ── Fluent 2 Neutral Color Ramp (Dark Theme) ───────────────────────────
# Based on official Fluent 2 grey palette for dark mode
# Mapping: colorNeutralBackground* → BG_*, colorNeutralForeground* → FG_*
# grey[N] references from Fluent 2 global tokens

# Background layers (darkest → lightest)
# Aligned with Fluent 2 colorNeutralBackground hierarchy
BG_SOLID: str = "#000000"            # grey[0] / black — deepest base (canvas, root)
BG_LAYER_1: str = "#242424"          # grey[4] — app background, base layer
BG_LAYER_2: str = "#2c2c2c"          # grey[8] — panels, secondary surfaces
BG_LAYER_3: str = "#363636"          # grey[12] — raised cards, content areas
BG_LAYER_4: str = "#3d3d3d"          # grey[16] — elevated surfaces, tooltips
BG_LAYER_5: str = "#484848"          # grey[20] — highest background (dialogs, overlays)

# Interactive surface states
BG_SUBTLE: str = "transparent"       # colorSubtleBackground rest (hover: grey[22])
BG_SUBTLE_HOVER: str = "rgba(255, 255, 255, 0.06)"     # grey[22] — subtle hover (list items, etc.)
BG_SUBTLE_PRESSED: str = "#2e2e2e"   # grey[18] — subtle pressed
BG_SUBTLE_SELECTED: str = "#333333"  # grey[20] — subtle selected

# Card surfaces (from colorNeutralCardBackground)
BG_CARD: str = "#3d3d3d"             # grey[20] rest
BG_CARD_HOVER: str = "#454545"       # grey[24] hover
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

# ── Typography (Fluent 2 Type Ramp) ───────────────────────────────────
# Based on https://fluent2.microsoft.design/typography
# Font family: Segoe UI Variable with fallback to Segoe UI
# Windows 10 may not have Segoe UI Variable — fallback ensures compatibility
FONT_FAMILY: str = '"Segoe UI Variable", "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif'
FONT_FAMILY_MONO: str = '"Consolas", "Courier New", monospace'

# Font Weights (Fluent 2 conventions)
FONT_WEIGHT_REGULAR: int = 400   # fontWeightRegular — default body text
FONT_WEIGHT_MEDIUM: int = 500    # fontWeightMedium — slight emphasis
FONT_WEIGHT_SEMIBOLD: int = 600  # fontWeightSemibold — headings, buttons
FONT_WEIGHT_BOLD: int = 700      # fontWeightBold — strong emphasis, display

# Type Ramp (font size / line height)
# Caption 2: 10px / 14px (Regular 400)
FONT_SIZE_CAPTION_2: int = 10
FONT_LINE_HEIGHT_CAPTION_2: int = 14

# Caption 1: 12px / 16px (Regular 400 or Semibold 600)
FONT_SIZE_CAPTION_1: int = 12
FONT_LINE_HEIGHT_CAPTION_1: int = 16

# Body 1: 14px / 20px (Regular 400 or Semibold 600) — default UI text
FONT_SIZE_BODY_1: int = 14
FONT_LINE_HEIGHT_BODY_1: int = 20

# Body 2: 16px / 22px (Regular 400)
FONT_SIZE_BODY_2: int = 16
FONT_LINE_HEIGHT_BODY_2: int = 22

# Subtitle 2: 20px / 28px (Semibold 600)
FONT_SIZE_SUBTITLE_2: int = 20
FONT_LINE_HEIGHT_SUBTITLE_2: int = 28

# Subtitle 1: 24px / 32px (Semibold 600)
FONT_SIZE_SUBTITLE_1: int = 24
FONT_LINE_HEIGHT_SUBTITLE_1: int = 32

# Title 3: 28px / 36px (Semibold 600)
FONT_SIZE_TITLE_3: int = 28
FONT_LINE_HEIGHT_TITLE_3: int = 36

# Title 2: 32px / 40px (Semibold 600)
FONT_SIZE_TITLE_2: int = 32
FONT_LINE_HEIGHT_TITLE_2: int = 40

# Title 1: 40px / 52px (Semibold 600)
FONT_SIZE_TITLE_1: int = 40
FONT_LINE_HEIGHT_TITLE_1: int = 52

# Display: 68px / 92px (Bold 700)
FONT_SIZE_DISPLAY: int = 68
FONT_LINE_HEIGHT_DISPLAY: int = 92

# Legacy aliases for backward compatibility (preserve original values)
# Keep these at their original sizes so existing QSS doesn't break
# Use new Fluent 2 tokens (FONT_SIZE_CAPTION_1, FONT_SIZE_BODY_1, etc.) for new code
FONT_SIZE_CAPTION: int = 11    # original value preserved
FONT_SIZE_BODY: int = 13       # original value preserved
FONT_SIZE_SUBTITLE: int = 15   # original value preserved
FONT_SIZE_TITLE: int = 16      # original value preserved
FONT_SIZE_HEADER: int = 20     # original value preserved

# ── Animation (Fluent 2 Motion Tokens) ────────────────────────────────
# Based on https://fluent2.microsoft.design/motion
# Duration tokens
DURATION_ULTRA_FAST: int = 50   # durationUltraFast — focus rings, micro feedback
DURATION_FASTER: int = 100      # durationFaster — icon state swaps, badge updates
DURATION_FAST: int = 150        # durationFast — button press, toggle, checkbox
DURATION_NORMAL: int = 200      # durationNormal — default hover/focus/state transitions
DURATION_GENTLE: int = 250      # durationGentle — content revealing, tooltip appear
DURATION_SLOW: int = 300        # durationSlow — drawer open, panel slide-in
DURATION_SLOWER: int = 400      # durationSlower — complex orchestrated sequences
DURATION_ULTRA_SLOW: int = 500  # durationUltraSlow — full-page transitions, hero reveals

# Easing curves (CSS cubic-bezier values for reference — Qt uses QEasingCurve enums)
# Qt mappings:
#   curveEasyEase → QEasingCurve.Type.OutCubic (default, smooth)
#   curveDecelerate → QEasingCurve.Type.OutQuad (entering elements)
#   curveAccelerate → QEasingCurve.Type.InQuad (exiting elements)
#   curveLinear → QEasingCurve.Type.Linear (loops, progress)
CURVE_EASY_EASE: str = "cubic-bezier(0.33, 0, 0.67, 1)"    # Elements moving within viewport
CURVE_EASY_EASE_MAX: str = "cubic-bezier(0.8, 0, 0.2, 1)"  # Emphasis, dramatic repositioning
CURVE_ACCELERATE: str = "cubic-bezier(0.9, 0.1, 1, 0.2)"   # Exiting screen (ease in, fast out)
CURVE_DECELERATE: str = "cubic-bezier(0.1, 0.9, 0.2, 1)"   # Entering screen (ease out, slow in)
CURVE_LINEAR: str = "linear"                                # Continuous repetitive motion

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
