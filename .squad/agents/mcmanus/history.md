# McManus — UI Dev History

## Recent Work

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
