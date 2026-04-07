# McManus — UI Dev History

## Recent Work

### 2026-04-07: Fluent 2 Typography, Shapes & Spacing (Issue #100)

**Task:** Apply Fluent 2 typography, shapes, spacing, and motion tokens  
**Outcome:** ✅ Complete — PR #105  
**Branch:** feat/issue-100-fluent2-typography

Implemented the complete Fluent 2 type ramp, shape system, spacing tokens, and motion tokens. This aligns FollowCursor's design system with Windows 11 and Microsoft's official Fluent 2 specifications.

**Implementation:**
- **Typography tokens** (`tokens.py`)
  - Full Fluent 2 type ramp: Caption2 (10/14) through Display (68/92)
  - Font family: Segoe UI Variable with fallback to Segoe UI for Windows 10
  - Font weight constants: Regular (400), Medium (500), Semibold (600), Bold (700)
  - Added line height tokens for each type level
  - Legacy aliases (FONT_SIZE_CAPTION, FONT_SIZE_BODY, etc.) preserved for backward compat
- **Spacing tokens** (`tokens.py`)
  - Extended from 7 tokens to 13 Fluent 2 spacer levels
  - New range: 2px (SPACE_XXS) to 64px (SPACE_64)
  - Granular steps: 2, 4, 6, 8, 10, 12, 16, 20, 24, 32, 40, 48, 64
  - Maps to Fluent 2 size20, size40, size60, size80, etc.
- **Shape tokens** (`tokens.py`)
  - RADIUS_NONE (0px) for edge-aligned elements
  - RADIUS_SMALL (4px) for buttons, inputs
  - RADIUS_MEDIUM (8px) for cards, panels
  - RADIUS_LARGE (12px) for sheets, popovers
  - RADIUS_XLARGE (16px) for extra-large containers
  - RADIUS_CIRCULAR (9999px) for avatars, status dots
- **Motion tokens** (`tokens.py`)
  - 8 duration levels: DURATION_ULTRA_FAST (50ms) to DURATION_ULTRA_SLOW (500ms)
  - 5 easing curves: CURVE_EASY_EASE, CURVE_DECELERATE, CURVE_ACCELERATE, CURVE_EASY_EASE_MAX, CURVE_LINEAR
  - CSS cubic-bezier references for future web/HTML export
- **Animation enhancements** (`fluent_effects.py`)
  - Added configurable easing parameter to install_hover_animation()
  - Updated default duration from DURATION_FAST (100ms) to DURATION_FASTER (100ms) for consistency
  - Added helper functions: get_entering_curve(), get_exiting_curve(), get_default_curve()
  - Maps Fluent 2 curves to Qt enums (OutQuad, InQuad, OutCubic)

**Testing:**
- ✅ All 375 tests pass
- ✅ No breaking changes — theme.py QSS inherits updated tokens automatically
- ✅ Legacy token aliases prevent any regression

**Key learnings:**
- Fluent 2 uses a 4px base grid but includes odd values (2, 6, 10) for icon alignment
- Type ramp line heights are critical for vertical rhythm
- Segoe UI Variable is Windows 11 only — fallbacks essential for Windows 10
- Motion tokens distinguish entering (decelerate) vs. exiting (accelerate) vs. in-viewport (ease)
- Qt easing curves map cleanly to Fluent 2 CSS bezier curves

**References:**
- https://fluent2.microsoft.design/typography
- https://fluent2.microsoft.design/shapes
- https://fluent2.microsoft.design/layout
- https://fluent2.microsoft.design/motion

### 2026-04-07: Fluent UI System Icons Integration (Issue #99)

**Task:** Replace all emoji icons with proper Fluent UI System Icons  
**Outcome:** ✅ Complete — PR #103  
**Branch:** feat/issue-99-fluent-icons

Replaced all emoji characters (⏺, ▶, ⏸, 💾, 🔍, ✂, 🎙, 🎬, ⬆, 🗑) with SVG icons from Microsoft's Fluent UI System Icons library. Emoji rendering is inconsistent across Windows versions and unprofessional.

**Implementation:**
- Created **icon_loader.py** module with theme-aware SVG loading
  - Reads SVG files from `followcursor/app/icons/` directory
  - Applies fill color dynamically using token references (regex replacement)
  - Caches loaded icons for performance (global dict)
  - Converts rgba() token strings to hex for SVG compatibility
  - Returns QIcon ready for use in Qt widgets
- Downloaded 17 SVG files from Fluent UI System Icons GitHub repo (20px size)
  - Regular variants: play, pause, record, save, search, cut, mic, video, arrow_upload, delete, add, folder_open
  - Filled variants: play, pause, record, save (for active/selected states)
- Replaced emoji in **main_window.py**:
  - Sidebar buttons: Record (filled), Edit (play), Open (folder_open), Save
  - Control bar: Record button with filled red icon
  - Context menus: Zoom (search), Delete (delete with danger color)
- Replaced emoji in **title_bar.py**:
  - Logo icon: Play filled in brand color
  - Export button: Arrow upload icon
  - Discard button: Delete icon
- Replaced emoji in **timeline_widget.py**:
  - Play/pause button: Dynamically swaps between play_filled and pause_filled
  - Context menus: Split (cut), Add Zoom (search), Add Voiceover (mic), Delete (delete)
- Replaced emoji in **editor_panel.py**:
  - Auto-detect chapters button: Video icon
- Replaced emoji in **preview_widget.py**:
  - Zoom context menu: Search icon

**Design approach:**
- Icons colored using token references (T.BRAND, T.FG_PRIMARY, T.DANGER)
- Filled variants for active states (play button switches to pause when playing)
- Sidebar buttons changed signature from text emoji to QIcon
- All menu items use setIcon() for consistent alignment

**Testing:**
- ✅ All 370 tests pass
- ✅ No visual regressions (icons align properly with text)

**Key learnings:**
- SVG color replacement via regex is simpler than QSvgRenderer colorization
- Icon caching critical for performance (20+ icons loaded per session)
- Filled vs. regular variants provide good visual hierarchy
- 20px size works well for both buttons and menu items

### 2026-04-07: Issue #98 Session Log (Orchestration Complete)

**Session:** 2026-04-07T10:34:00Z  
**Task:** Adopt Fluent 2 color system and elevation tokens (Issue #98)  
**Outcome:** ✅ Complete — PR #102

Comprehensive implementation of Fluent 2 Phase 3, aligning FollowCursor's color system with Microsoft's official design spec. Replaced Phase 1's custom purple-tinted dark palette with authentic Fluent 2 grey ramps and proper 5-layer elevation architecture.

**Key deliverables:**
- tokens.py: Full Fluent 2 grey palette, 5-layer shadow system, semantic color/stroke/background tokens
- fluent_effects.py: Expanded shadow levels from 2 to 7 entries (layer0-4 + legacy aliases)
- test_fluent_effects.py: 3 opacity fixes, 5 new layer validation tests
- Backward compatibility: All Phase 1 token names maintained as aliases

**Results:**
- ✅ All 375 tests pass
- ✅ Zero breaking changes
- ✅ PR #102 ready for team review
- ✅ Branch: feat/issue-98-fluent2-colors

**References:**
- Fluent 2 Color System: https://fluent2.microsoft.design/color
- Elevation Spec: https://fluent2.microsoft.design/elevation
- Squad decisions.md: mcmanus-fluent2-colors.md

### 2026-04-06: Interactive Annotations (Issue #54)

Implemented complete annotation system for text, arrows, and highlights.

**Models** (models.py):
- Added TextAnnotation, ArrowAnnotation, HighlightBox dataclasses
- Created AnnotationCollection container class
- Full serialization support with 	o_dict() / rom_dict() methods
- Normalized coordinates (0-1) for resolution independence

**Renderer** (nnotation_renderer.py):
- Dual-pipeline architecture: QPainter for preview, OpenCV for export
- Followed established patterns from cursor_renderer.py and keystroke_renderer.py
- Proper layering: highlights (back) → arrows → text (front)
- Timeline-aware rendering (only visible during time range)
- Alpha blending for highlight boxes and text backgrounds

**UI** (ditor_panel.py):
- Added ANNOTATIONS collapsible section with three action buttons
- Scrollable annotation list with type icons and delete buttons
- Real-time annotation placement at playhead position
- Default 3-second duration for new annotations
- Integrated into editor panel signal system

**Integration**:
- ideo_exporter.py: Added annotation rendering to both normal and speed-adjusted frame loops
- compositor.py: Updated compose_scene() with annotation support (handles zoom-video-only mode)
- preview_widget.py: Added set_annotations() method and state tracking
- project_file.py: Full save/load support for AnnotationCollection
- main_window.py: State management, signal routing, export/preview wiring

**Testing**: All 58 existing tests pass.

## Learnings

### 2026-07-23: Fluent 2 Phase 3 — Authentic Color System & Elevation (Issue #98)

**Context**: Prior phases built a token system but used custom purple-tinted dark palette. This phase aligns with the *official* Fluent 2 spec using Microsoft's grey ramps and elevation formula.

**Research approach**:
- Fetched official Fluent 2 docs: color system, color tokens, elevation spec
- Web-searched for detailed token mappings and dark theme shadow values
- Discovered Fluent 2 uses grey[N] notation (grey[0]=black, grey[16], grey[84]=light grey)
- Found exact shadow formulas: Shadow2 (2px blur, 1px offset), Shadow4, Shadow8, Shadow16
- Dark theme shadow opacity: 28% key + 24% ambient (not the 25%/35% I had before)

**tokens.py changes**:
- **Color ramp**: Replaced custom hex with Fluent 2 grey palette
  - BG_SOLID (#000000) = grey[0]
  - BG_LAYER_1 (#141414) = grey[4] — app canvas
  - BG_LAYER_2 (#1f1f1f) = grey[8] — panels
  - BG_LAYER_3 (#292929) = grey[12] — cards
  - BG_LAYER_4 (#333333) = grey[16] — elevated
  - BG_LAYER_5 (#3d3d3d) = grey[20] — highest
- **Foreground**: FG_1 (white), FG_2 (grey[84]), FG_3 (grey[68]), FG_4 (grey[60]), FG_DISABLED (grey[36])
- **Strokes**: STROKE_ACCESSIBLE (grey[68]), STROKE_1 (grey[40]), STROKE_2 (grey[32]), STROKE_SUBTLE (grey[4])
- **5-layer elevation** (not just 2):
  - SHADOW_LAYER_0: No shadow (flat)
  - SHADOW_LAYER_1: 2px blur, 1px offset (Shadow2)
  - SHADOW_LAYER_2: 4px blur, 2px offset (Shadow4)
  - SHADOW_LAYER_3: 8px blur, 4px offset (Shadow8)
  - SHADOW_LAYER_4: 16px blur, 8px offset (Shadow16)
  - All use 28% key + 24% ambient opacity (dark theme spec)
- **Semantic status colors**: Updated with Fluent 2 cranberry (danger), green (success), orange (warning), blue (info) ramps
- **Legacy aliases**: BG_CANVAS → BG_LAYER_1, BG_PANEL → BG_LAYER_2, etc. (backward compat)

**fluent_effects.py**:
- Expanded `_SHADOW_LEVELS` from 2 to 7 entries (layer0-4 + subtle/medium aliases)
- Default shadow level changed from "subtle" to "layer2" (cards)
- Updated docstring with all layer options and use cases

**test_fluent_effects.py**:
- Fixed shadow opacity assertions (71 for 0.28 alpha, not 63 or 89)
- Added 5 new tests for each Fluent 2 layer (layer0-4)
- Verified blur/offset values match spec exactly

**Key decisions**:
1. **Backwards compatibility is critical** — kept all legacy token names as aliases so existing QSS doesn't break
2. **Fluent 2 naming convention** — used "layer0-4" instead of inventing custom names, makes docs alignment clear
3. **No visual redesign** — this is a *spec alignment* pass, not a UX change. The theme still looks similar but now follows official Fluent 2 values
4. **Grey ramp abstraction** — used actual grey[N] hex values in comments, but exposed them as semantic tokens (BG_LAYER_*, FG_*, STROKE_*)
5. **Material effects stub** — added MATERIAL_OVERLAY_ALPHA/CARD_ALPHA tokens for future acrylic/mica work

**Testing**: All 375 tests pass (3 fluent_effects tests updated, 5 new layer tests added).

**References saved**:
- https://fluent2.microsoft.design/color
- https://fluent2.microsoft.design/color-tokens/
- https://fluent2.microsoft.design/elevation

**Branch**: `feat/issue-98-fluent2-colors`  
**PR**: #102
### 2026-04-07: Documentation Quality Pass (Issue #97)

Performed comprehensive quality audit on the mkdocs documentation site. Key findings:

**Test suite growth**: Since the last docs rewrite (PR #95), the test suite grew from 359 to 386 tests — a 7.5% increase across 14 test files. This required updating CONTRIBUTING.md to reflect the accurate current count.

**Code block formatting**: Found 7 ASCII diagram blocks in ARCHITECTURE.md that lacked language hints. Added `text` as the language specifier to enable proper syntax highlighting in the rendered docs. MkDocs/Material requires explicit language hints on all fenced code blocks.

**Component map completeness**: The ARCHITECTURE.md component map was missing `app/utils.py` — a helper module for video/image processing utilities. Added it to maintain an accurate file inventory for contributors.

**Documentation accuracy verification strategy**: Rather than relying on memory, verified feature descriptions by running Python snippets against the live codebase (e.g., `from app.backgrounds import PRESETS; len(PRESETS)`). This confirmed all quantitative claims (84 backgrounds, 5 frames, 386 tests) match v0.9.0 reality.

**Cross-reference validation**: Used grep to extract all internal anchor links (`#ai-smart-zoom`, `#live-zoom-during-recording`) and verified matching headers exist. All `.md` links in the nav structure resolve correctly.

**No formatting artifacts found**: No double-apostrophe glyphs, control characters, or single-backtick multi-line blocks discovered. The original rewrite (PR #95) was already high-quality — this pass was primarily about version drift corrections.

**Takeaway**: Documentation should be treated as code — verify claims against the source of truth (the actual codebase), not assumptions. Periodic audits catch version drift before it becomes stale.

### 2026-07-23: Complete Documentation Rewrite (PR #95)

Rewrote all 5 docs pages + mkdocs.yml for the GitHub Pages site (mkdocs-material).

**Files changed (8):**
- `docs/index.md` — Landing page with feature grid (material card layout)
- `docs/QUICKSTART.md` — Step-by-step getting started (install, record, edit, export)
- `docs/USER_GUIDE.md` — Complete feature reference covering: recording, playback, zoom (auto/AI/manual/pan), click events, visual enhancements (backgrounds, frames, cursor, keystroke overlay, annotations), export (MP4/GIF), trimming, segments, undo/redo, AI (zoom + TTS voiceover), chapters, projects, settings, shortcuts
- `docs/ARCHITECTURE.md` — System overview, data model, capture backends, zoom engine, activity analyzer, AI service, export pipeline, compositor, design system (tokens.py/Fluent 2), input tracking, UI architecture, threading model, component map
- `docs/CONTRIBUTING.md` — Dev setup, coding conventions (tokens, QSS, signals), testing (359 tests, VS Code task), security, branching, versioning, CI/CD
- `mkdocs.yml` — Updated site_url to https://sabbour.me/followcursor, added markdown extensions (admonitions, superfences, tabbed, attr_list, md_in_html, toc)
- `README.md` + `followcursor/README.md` — Added docs site link

**Key approach:** Read all source files (models.py, main_window.py, video_exporter.py, zoom_engine.py, activity_analyzer.py, ai_service.py, screen_recorder.py, cursor_renderer.py, keystroke_renderer.py, annotation_renderer.py, backgrounds.py, frames.py, project_file.py, credentials.py, tokens.py, fluent_effects.py) to build a complete feature inventory before writing. This ensured no features were missed (e.g., chapters, pan path points, keystroke overlay, DPAPI credentials, design tokens, VoiceoverSegment rate/volume).

### 2026-07-22: Fluent 2 Phase 2 — Visual Polish (Shadows, Animations, Focus)

**fluent_effects.py** — New reusable effects module:
- `apply_shadow(widget, level)` — applies QGraphicsDropShadowEffect with "subtle" (4px blur) or "medium" (8px blur) levels
- `install_hover_animation(widget, prop, start, end)` — attaches QPropertyAnimation via event filter, no subclassing needed
- `install_focus_ring(widget)` — toggles brand-coloured glow on keyboard focus via event filter
- `HoverAnimationFilter` / `FocusRingFilter` — reusable QObject event filters
- `_parse_rgba()` — helper to convert token rgba strings to QColor

**tokens.py** — Added Phase 2 tokens:
- Focus ring: FOCUS_RING_WIDTH=2, FOCUS_RING_OFFSET=2
- Scrollbar: SCROLLBAR_THIN=6, SCROLLBAR_WIDE=12, SCROLLBAR_MIN_HEIGHT=24

**theme.py** — Focus & scrollbar enhancements:
- QPushButton/QComboBox/QLineEdit/QTextEdit :focus rules with 2px BRAND border
- Vertical + horizontal scrollbar styling with hover expansion (6px→12px)
- Pressed handle state and rounded track corners

**editor_panel.py** — Migrated ~30 hardcoded hex colors to token references:
- Collapsible section headers, scrollbar overrides, checkbox styling
- Menu popups, about dialog, annotation list items
- Background swatch picker (all `#8b5cf6` → `T.BRAND`, `6px` → `T.RADIUS_SMALL`)

**source_picker.py** — Applied shadows + token styles:
- Cards get `apply_shadow("subtle")`, dialog gets `apply_shadow("medium")`
- Tab bar colors migrated from hardcoded hex to tokens
- Thumbnail label background uses `T.BG_CANVAS` + `T.RADIUS_SMALL`

**Key decisions:**
- QGraphicsDropShadowEffect is exclusive per widget — focus ring (glow) and shadow can't coexist. Use shadow on passive surfaces, focus ring on interactive controls.
- Event filters for hover/focus avoid subclassing every widget. Lightweight and composable.
- Qt QSS doesn't support CSS `outline` properly — implemented focus via border instead.
- Scrollbar hover width expansion works natively in QSS (width property in :hover pseudo-state).

**Testing**: All 347 tests pass (334 existing + 13 new for fluent_effects).

### 2026-07-22: Fluent 2 Phase 1 — Design Tokens & Theme Normalization

**tokens.py** — New centralized design token module:
- Spacing tokens on 4px grid (XXS=4 through XXL=48)
- Corner radius: RADIUS_SMALL=4 (controls), RADIUS_MEDIUM=8 (containers)
- Full semantic color palette: 5 background layers, 3 border tiers, 4 foreground levels
- Brand/accent: BRAND, BRAND_HOVER, BRAND_ACTIVE + translucent variants
- Status colors: SUCCESS, DANGER (with 6 variants), WARNING (#f59e0b), INFO (#3b82f6)
- Special surfaces: dialog, card, overlay, close button, discard button
- Typography: FONT_FAMILY, 5 size tokens (caption 11 → header 20)
- Animation durations: FAST=100ms, NORMAL=200ms, SLOW=300ms
- Shadow parameters for 2 elevation levels

**theme.py** — Refactored to use token system:
- Converted from static string to f-string with `from . import tokens as T` references
- All QSS `{`/`}` escaped as `{{`/`}}` for f-string compatibility
- Normalized all padding/margin to 4px grid: 2→4, 6→8, 10→8, 14→16, 18→16
- Unified corner radii: eliminated 6px, 10px, 12px, 18px → 4px or 8px only (circles at 3px preserved)
- Added Warning/Info status dot styles (#StatusDotWarning, #StatusDotInfo)
- Added :disabled states for ExportBtn, DiscardBtn, CtrlBtn, PlayBtn

**Testing**: All 334 existing tests pass.

### 2026-01-20: Fluent 2 / Windows 11 Design Research

**Windows 11 Design System:**
- Uses Fluent 2 with 4px base spacing grid, 4px/8px corner radius standards
- Typography: Segoe UI Variable with defined type ramp (Header 46px/200, Body 15px/400, Caption 12px/400)
- Materials: Mica (opaque wallpaper tint for backgrounds) and Acrylic (frosted glass for transient UI)
- Motion: 100ms ease-out for state changes, 300ms for content reveals
- Color system: Semantic tokens (`colorBrandBackground`, `colorNeutralForeground1`, etc.) with theme-aware values

**Fluent 2 Component Catalog:**
- Mapped 50+ Fluent components to Qt equivalents (Button→QPushButton, Switch→Custom, Slider→QSlider, etc.)
- High priority for video editor: Button, Slider, Tablist, Combobox, Progress Bar, Dialog, Toolbar, Tooltip
- Some components need custom QPainter (Switch, Badge, Persona), others work with QSS (Button, Input, Card)

**PySide6-Fluent-Widgets Library:**
- Mature library (1000+ commits) with GPLv3 license (compatible with FollowCursor)
- Provides 50+ Fluent-styled widgets with acrylic blur, animations, light/dark themes
- Homepage: https://qfluentwidgets.com/ | PyPI: https://pypi.org/project/PySide6-Fluent-Widgets/
- Installation: `pip install "PySide6-Fluent-Widgets[full]"`
- Includes: NavigationInterface, FluentDialog, FluentCard, CommandBar, etc.

**Current Theme Analysis:**
- ✅ Strengths: Segoe UI Variable, dark palette, purple accent (#8b5cf6), border radius on most elements
- ❌ Gaps: Inconsistent spacing (not on 4px grid), mixed corner radius (6-12px), no design tokens, missing animations, no drop shadows, no focus indicators
- Current spacing values: 4px, 6px, 8px, 12px, 14px, 16px, 18px, 20px — need normalization
- Current radius values: 4px, 6px, 8px, 10px, 12px, 18px — need to standardize to 4px/8px

**Implementation Strategy:**
- **Hybrid approach:** Use library for standard UI (navigation, dialogs, cards), custom QSS/QPainter for specialized (timeline, preview, title bar)
- **Design token system:** Create `app/tokens.py` with constants for spacing (4/8/12/16/24/32px), radius (4/8px), colors (semantic names)
- **Quick wins:** Normalize spacing to 4px grid, unify corner radius to 4px/8px, add missing status colors (Warning #f59e0b, Info #3b82f6)
- **Phased rollout:** Pilot library in source picker → refine custom QSS → token system → animations/shadows → accessibility

**Key Qt/PySide6 Techniques:**
- QSS supports `border-radius` for rounded corners but not CSS transitions (need QPropertyAnimation)
- QPainter required for: custom shapes (pill switches), gradients, semi-transparent overlays
- QGraphicsDropShadowEffect for elevation shadows (4px blur, 2px offset for subtle depth)
- QStyle/QProxyStyle for system-wide appearance changes (alternative to per-widget styling)
- Acrylic blur requires native OS APIs (DWM on Windows) — library handles this

**File Paths:**
- Theme: `followcursor/app/theme.py` — single DARK_THEME QSS string
- Widgets: `followcursor/app/widgets/` — title_bar, editor_panel, preview, timeline, source_picker
- Style data: `followcursor/app/backgrounds.py`, `followcursor/app/frames.py` — presets for compositor

**Next Steps:**
- Decision needed on hybrid approach (library + custom QSS)
- Pilot PySide6-Fluent-Widgets in source picker dialog
- Create design token system for spacing/color/radius consistency
- Add QPropertyAnimation for hover states (100ms ease-out)
- Audit accessibility (focus indicators, keyboard nav, contrast ratios)

1. **Dual-Pipeline Pattern**: The cursor and keystroke renderers established a clean pattern with separate QPainter and OpenCV render functions. Following this pattern made integration straightforward and maintainable.

2. **Normalized Coordinates**: Using 0-1 normalized coordinates for annotation positions ensures annotations work correctly regardless of source resolution or export dimensions. Critical for cross-resolution compatibility.

3. **Timeline Integration**: Annotations need the current playhead time for proper placement. Connected _on_seek() in main_window to update both preview and editor panel with set_current_time().

4. **Signal-Driven Architecture**: FollowCursor uses Qt signals for all inter-component communication. Added three new signals to EditorPanel: nnotation_added, nnotation_removed, nnotation_updated.

5. **State Management Pattern**: Followed existing patterns for state variables (self._annotations), save/load integration, and export parameter passing. Consistency with _keystroke_config and _click_preset made wiring straightforward.

6. **Layering Order**: Rendering order matters for visual hierarchy. Highlights must be drawn first (background), then arrows, then text (foreground) for proper layering in both preview and export.

7. **Alpha Blending**: Highlight boxes and text backgrounds require proper alpha blending. OpenCV uses cv2.addWeighted() with overlay technique; QPainter uses QColor.setAlphaF().

8. **Zoom-Video-Only Mode**: The compositor has special handling for frameless + zoom mode (virtual screen rect calculation). Had to handle this case separately in annotation rendering.

9. **List Management**: Used insertWidget(count - 1) pattern to keep annotation items above the stretch spacer in the scrollable list. Delete handling removes both from UI and data model.

10. **Factory Pattern**: All annotation models use static create() factory methods that auto-generate UUIDs. Follows the established pattern from ZoomKeyframe, VideoSegment, etc.

## Technical Decisions

- **Coordinate System**: Normalized (0-1) rather than absolute pixels for resolution independence
- **Rendering Pipeline**: Separate functions for QPainter (preview) and OpenCV (export)
- **Default Duration**: 3 seconds for new annotations (reasonable visibility window)
- **Storage Format**: Full AnnotationCollection serialized as nested dict in project.json
- **UI Layout**: Scrollable list with max-height of 200px to prevent panel overflow
- **Color Defaults**: Yellow (#FFCC00) for arrows/highlights, white text with dark background

## Code Organization

The annotation feature follows FollowCursor's established patterns:
- Data models in models.py with serialization support
- Dual-pipeline renderer in dedicated module
- UI controls in collapsible section within editor panel
- State management in main window
- Integration points: video exporter, compositor, project file, preview widget

This organization ensures maintainability and consistency with the existing codebase.

## Learnings

### 2026-04-07: Fluent 2 Design Token Alignment

**Context:** Issue #100 required adopting the full Fluent 2 typography, shapes, spacing, and motion specifications.

**Key takeaways:**
1. **Type ramp precision matters** — Fluent 2 uses specific font size/line height pairs (e.g., Body1 = 14/20, not 14/18). Line height ensures vertical rhythm.
2. **Spacing granularity** — While the 4px grid is the base, Fluent 2 includes 2px, 6px, and 10px steps for tight icon/text alignment scenarios.
3. **Shape token naming** — Fluent uses "Global-Corner-Radius-40" (4px), not "small". We aliased RADIUS_SMALL → 4px for readability but documented the official token names in comments.
4. **Motion intent-based design** — Fluent 2 distinguishes entering (decelerate/slow in), exiting (accelerate/fast out), and in-viewport (ease). Helper functions (get_entering_curve, get_exiting_curve) make this explicit.
5. **Windows 10 font fallback** — Segoe UI Variable is Windows 11 only. Always include "Segoe UI" as the first fallback.
6. **Qt easing curve mapping** — Fluent 2's curveDecelerate = Qt's OutQuad, curveAccelerate = InQuad, curveEasyEase = OutCubic.
7. **Backward compatibility strategy** — Legacy token names (FONT_SIZE_BODY, SPACE_XXS, etc.) preserved as aliases. This prevents breaking existing QSS/widget code while adopting the new spec.

**Future work:**
- Phase 4 (acrylic/mica materials) can now use MATERIAL_OVERLAY_ALPHA and MATERIAL_CARD_ALPHA tokens
- Animation helpers (get_entering_curve, get_exiting_curve) ready for fade-in/fade-out widget transitions
- Type ramp supports future UI scaling/accessibility features

### 2026-04-07: Fluent 2 Component Patterns (Issue #101)

**Task:** Align all PySide6 widget styling with Fluent 2 component patterns  
**Outcome:** ✅ Complete — PR #107  
**Branch:** feat/issue-101-fluent2-widgets

Restyled all widgets to match official Microsoft Fluent 2 component patterns. This builds on the previous foundation work (color tokens #98, typography/shapes #100, icons #99) to deliver production-quality Windows 11-style components.

**Implementation:**
- **Buttons** — Implemented all Fluent 2 button appearances:
  - Secondary (default): `BG_LAYER_3` background, `STROKE_1` border, `RADIUS_SMALL` (4px) corners
  - Primary: `BRAND` background, no border, white text (Export, Save, Record buttons)
  - Subtle: Transparent background, `STROKE_1` border (Discard button)
  - Transparent: No background or border, hover uses `BG_SUBTLE_HOVER` (title bar, sidebar, skip buttons)
  - All buttons: 6-16px padding, Semibold/Medium weight, proper hover/pressed/disabled states
- **Tabs** (source picker):
  - Applied Fluent 2 TabList pattern: transparent background, 2px bottom border for selection
  - Selected tab: `BRAND` underline, Semibold weight, `FG_PRIMARY` color
  - Hover: `BG_SUBTLE_HOVER` background
  - Min height 40px, proper padding (8-16px horizontal)
- **Cards** (preview panel, source picker):
  - Base: `BG_CARD` background, 1px `STROKE_1` border, 8px radius
  - Hover: `BG_CARD_HOVER` background, `STROKE_ACCESSIBLE` border
  - Selected: 2px `BRAND` border, `BG_CARD_SELECTED` background
  - 8px internal padding
- **Inputs** (QLineEdit, QTextEdit):
  - `BG_LAYER_2` background, 1px `STROKE_1` border, 4px radius
  - Hover: `STROKE_ACCESSIBLE` border
  - Focus: 2px `BRAND` outline with 2px offset (Fluent 2 spec)
  - Disabled: `BG_LAYER_1` background, `FG_DISABLED` text
- **Combobox/Dropdown**:
  - Same styling as inputs for consistency
  - Dropdown menu: `BG_LAYER_4` with 8px radius, `BG_SUBTLE_HOVER` on item hover
  - Item padding: 6-12px, min-height 32px
- **SpinBox**:
  - Same input styling, transparent up/down buttons with hover state
- **Slider**:
  - 4px track height, 16px circular handle with 2px `BRAND` border
  - Active range uses `BRAND` color
  - Handle hover/pressed states change to `BRAND_HOVER`/`BRAND_ACTIVE`
  - Focus: 2px outline with 2px offset
- **Checkbox**:
  - 16×16px indicator, 1px border, 4px radius
  - Checked: `BRAND` background and border
  - Hover: `STROKE_ACCESSIBLE` border, `BG_LAYER_3` background
- **Menus**:
  - `BG_LAYER_4` background, 1px border, 8px radius
  - Items: transparent background, 6-12px padding, 4px radius, min-height 32px
  - Hover: `BG_SUBTLE_HOVER`
  - Separator: 1px `STROKE_2` line with 4px margin
- **Dialogs**:
  - `BG_LAYER_3` background, 1px border, 12px radius (RADIUS_LARGE)
- **Progress bar**:
  - 4px height, 2px radius
  - Track: `BG_LAYER_2`, Fill: `BRAND`
- **Scrollbars**:
  - Minimal 6px width (expands to 12px on hover)
  - Handle: `STROKE_1` (rest), `STROKE_ACCESSIBLE` (hover), `FG_2` (pressed)
  - Transparent background, 4px radius
- **Tooltips**:
  - `BG_LAYER_5` background, 1px border, 8px radius
  - Caption 1 size (12px/16px), 6-8px padding
- **Focus rings** (keyboard accessibility):
  - Visual target is a Fluent 2-style `BRAND` focus indicator for keyboard navigation
  - Current implementation is mixed: `QPushButton:focus` uses a QSS border/padding workaround, while other widgets still rely on `install_focus_ring()` (`QGraphicsDropShadowEffect`) because QSS `outline`/offset is not reliable across Qt widgets
  - Applied across interactive controls including buttons, inputs, combobox, spinbox, slider, and tabs, with the exact rendering method varying by widget

**App-Specific Widgets:**
- Title bar buttons: Subtle transparent style, 40×32px, 4px radius
- Sidebar nav buttons: Transparent with brand translucent active state, 64×64px, 8px radius
- Control bar buttons: Secondary style, 36px height
- Record button: Primary danger style, 48px height, 8px radius, 32px horizontal padding
- Keyframe items: Card style with hover border color change
- Timeline play button: Secondary style, 44×44px circular
- Status dots: 6×6px circular indicators

**Typography Updates:**
- Migrated from legacy font sizes (FONT_SIZE_BODY, FONT_SIZE_CAPTION) to Fluent 2 type ramp
- Body 1: 14px/20px (primary UI text)
- Caption 1: 12px/16px (labels, captions)
- Subtitle 2: 20px/28px (large buttons, headings)
- Font weights: Regular (400), Medium (500), Semibold (600), Bold (700)

**Design Token References:**
- Theme/design-system QSS uses tokens from `tokens.py`; some widget-local style strings may still contain hardcoded values
- Spacing: `SPACE_6` (6px), `SPACE_SM` (8px), `SPACE_MD` (12px), `SPACE_LG` (16px), `SPACE_XL` (24px), `SPACE_XXL` (32px)
- Radii: `RADIUS_SMALL` (4px), `RADIUS_MEDIUM` (8px), `RADIUS_LARGE` (12px)
- Colors: Fluent 2 neutral ramp (`BG_LAYER_1-5`, `FG_1-4`, `STROKE_1-2`, `STROKE_ACCESSIBLE`)
- Semantic: `BRAND`, `DANGER`, `SUCCESS`, `WARNING`, `INFO` with full state variants

**Testing:**
- ✅ All 375 tests pass
- ✅ No breaking changes — backward-compatible selectors preserved
- ✅ Verified all interactive states (hover, pressed, focus, disabled)

**Key learnings:**
- QSS outline property works for focus rings with offset (equivalent to CSS outline-offset)
- PySide6 QComboBox dropdown menus styled via `QAbstractItemView` child selector
- Slider handle margins must be negative to center properly on track
- Tabs need transparent background to avoid visual glitches during selection transition
- Menu item padding must account for icon space even when no icon present
- Focus rings should use outline (not border) to avoid layout shift
- Progress bar chunk styling requires exact same border-radius as container for clean edges
- Scrollbar handle needs explicit min-height/min-width to prevent collapse

**Reference:**
- https://fluent2.microsoft.design/components/web/react/

### 2026-07-25: Source Picker Fluent 2 Alignment

**Context:** The source picker dialog was the last widget not fully aligned with the Fluent 2 migration (PRs #98–#107).

**Key takeaways:**
1. **Inline QSS is a Fluent 2 anti-pattern** — The dialog had 11 lines of inline `setStyleSheet()` on the tab widget that overrode the global Fluent 2 tab styles with legacy values (wrong background, missing hover state, legacy font size). Removing inline QSS and relying on the global theme fixed all inconsistencies at once.
2. **Scoped QSS for container overrides** — When a dialog needs its tab pane background to be transparent (rather than the global `BG_LAYER_1`), add a scoped `#SourcePickerDialog QTabWidget::pane` rule in theme.py — don't use inline styles.
3. **Legacy token drift** — The dialog title used `FONT_SIZE_HEADER` (legacy 20px alias) and hardcoded weight `600`. While the values happened to match, using the Fluent 2 tokens (`FONT_SIZE_SUBTITLE_2`, `FONT_WEIGHT_SEMIBOLD`) is correct for consistency and future-proofing.
4. **Non-standard control heights** — The Refresh button had `setFixedHeight(28)` which doesn't match any Fluent 2 control height. Removing it lets the `CtrlBtn` QSS (36px) apply, consistent with all other secondary buttons.

