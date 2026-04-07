# Decisions Archive

## PR Review Fixes — Backend (Fenster, 2026-01-20)

**Status:** Applied | **Items:** 6 fixes + 12 prior resolutions

### Key Architectural Choices

1. **Modifier VKs now recorded**
   - Removed modifier VK codes (Shift/Ctrl/Alt/Win) from `_IGNORE_VKS` in keyboard_tracker
   - Trade-off: correct shortcut detection vs. slightly larger project files and broader privacy surface
   - Documented privacy implications in module docstring

2. **Chapter END time computation**
   - Changed from hardcoded `START + 1000` to computing END from next chapter's start time
   - Added `-f ffmetadata` and `-map_chapters` flags so ffmpeg interprets metadata correctly
   - Last chapter's END uses trimmed video duration

3. **Z-order change**
   - Moved annotation rendering BEFORE cursor/click rendering in main frame loop and extra-frames loop
   - New order: video → annotations → cursor → click effects → keystrokes

4. **Near-cursor keystroke placement**
   - Implemented actual cursor-relative positioning using `KeyEvent.x`/`KeyEvent.y` data
   - Falls back to bottom-center with debug log when no cursor data available

5. **JSON decoding error handling**
   - Confirmed `json.loads()` in `project_file.py` already inside try/except with `JSONDecodeError`
   - No change needed — already robust

## PR Review Fixes — UI & Docs (McManus, 2026-04-06)

**Status:** Applied | **Items:** 25 fixes + 2 prior resolutions + 1 new test

### Key Architectural Choices

1. **Keystroke rendering in preview**
   - Added `key_events` and `keystroke_config` parameters to `compose_scene()` and preview widget
   - Extends compositor's public API but keeps keystroke rendering consistent between preview and export
   - Alternative (rendering outside compositor) would duplicate zoom/clip logic

2. **Annotation z-order alignment**
   - Moved annotations to render **before** cursor and click effects in `compose_scene()`
   - Order: video → annotations → cursor → clicks → keystrokes
   - Ensures cursor/clicks always visible on top of annotations

3. **Single overlay allocation in annotation renderer**
   - `render_annotations_cv` allocates one shared overlay copy per frame call instead of per-annotation
   - Each annotation blends its region and resets overlay for next one
   - Avoids O(n) full-frame copies for n annotations per frame

4. **HighlightBox opacity precedence**
   - Documented that `opacity` takes precedence over color alpha in both QPainter and CV renderers
   - No runtime behavior change — both renderers already used `opacity`
   - Color's alpha channel effectively ignored

---
*All decisions applied as of 2026-04-07T01:30:06Z*

## Fluent 2 Design Research (McManus, 2026-04-07)

**Status:** Complete | **Research Type:** UI Design & Windows 11 Alignment

### Summary

Comprehensive analysis of Windows 11 Fluent 2 design system and PySide6 implementation strategies. Full research document in .squad/agents/mcmanus/fluent2-research.md.

### Key Findings

1. **PySide6-Fluent-Widgets:** Mature, GPLv3-licensed library with 50+ Fluent-styled components (navigation, dialogs, cards, inputs). Supports acrylic effects, animations, and light/dark themes.

2. **Current FollowCursor Theme:** 70% aligned with Fluent 2 — uses Segoe UI Variable and modern dark palette, but needs:
    - Spacing normalization (4px grid)
    - Corner radius unification (4px/8px)
    - Drop shadows and state animations
    - Status colors (Warning/Info)

3. **Recommended Hybrid Approach:**
    - **Library:** Navigation sidebar, dialogs, source picker, standard controls (combobox, slider)
    - **Custom QSS:** Timeline (specialized), preview widget (compositing), title bar (frameless)
    - **Design tokens:** Create 	okens.py for spacing, radius, colors

4. **Implementation Phases:**
    - Phase 1: Pilot PySide6-Fluent-Widgets in source picker (1–2 weeks)
    - Phase 2: Refine custom QSS with spacing/radius fixes (2–3 weeks)
    - Phase 3: Design token system (1 week)
    - Phase 4: Animations & shadows (1 week)
    - Phase 5: Accessibility & polish (1 week)

5. **Quick Wins:**
    - Normalize spacing to 4px grid
    - Unify corner radius (4px elements, 8px containers)
    - Add semantic color tokens

## User Directive (Ahmed Sabbour, 2026-04-07)

**Status:** Captured | **Type:** Development Workflow

### Directive

Create branches and worktrees before major work. All significant changes should be developed on a dedicated branch with a git worktree, not directly on main.

**Rationale:** User request — established to maintain clean main branch and enable parallel development.

*Updated: 2026-04-07T07:33:49Z*

## Fluent 2 Phase 1 — Design Token Architecture (McManus, 2026-04-07)

**Status:** Applied | **Implementation:** Complete

### Context

FollowCursor's theme.py used hardcoded hex colors, inconsistent spacing (2–28px, not on grid), and mixed corner radii (3–18px). Phase 1 of the Fluent 2 alignment creates a token-based architecture.

### Decisions

1. **Token module at `followcursor/app/tokens.py`** — all design constants live here, imported as `T` by theme.py. No other module should hardcode color hex or spacing values.

2. **Spacing normalized to 4px grid** — named tokens: XXS=4, XS=8, SM=12, MD=16, LG=24, XL=32, XXL=48. Padding/margin values that were off-grid (2, 6, 10, 14, 18px) snapped to the nearest token.

3. **Corner radii unified** — RADIUS_SMALL=4px for buttons/inputs, RADIUS_MEDIUM=8px for containers/dialogs. Circular elements (status dots, scrollbar) keep half-width radius since those are shapes, not corners.

4. **Warning (#f59e0b) and Info (#3b82f6) status colors added** — with hover variants. Status dot QSS rules added so widgets can use `#StatusDotWarning` / `#StatusDotInfo`.

5. **Disabled states added** — ExportBtn, DiscardBtn, CtrlBtn, PlayBtn now have `:disabled` QSS rules using `BRAND_DISABLED`/`FG_DISABLED` tokens.

### Impact

- Theme refactor only — no widget code changes, no behavioral changes
- All 334 tests pass unchanged
- Future theme work should modify `tokens.py` values, not hardcode in QSS
- Branch: `feat/fluent2-phase1`

---
*All decisions applied as of 2026-04-07T07:49:22Z*

## Fluent 2 Color System & Elevation Adoption (McManus, 2026-07-23)

**Status:** Implemented | **PR:** #102 | **Issue:** #98

### Context

FollowCursor's Phase 1 token system (created Jan 2026) introduced semantic color names and spacing normalization, but used a custom purple-tinted dark palette. Phase 3 replaces these with authentic Fluent 2 values from Microsoft's design spec.

### Research Findings

#### Official Fluent 2 Palette Structure

1. **Neutral Colors**: grey[0] (black) through grey[100] (white)
   - Dark theme backgrounds use grey[4] → grey[20] range (lighter = elevated)
   - Dark theme text uses white → grey[36] range (darker = disabled)
   - Strokes use grey[4] (subtle) → grey[68] (accessible)

2. **Elevation System**: 5 shadow layers (not 2)
   - Shadow2: 2px blur, 1px offset — buttons, minimal cards
   - Shadow4: 4px blur, 2px offset — cards, list items
   - Shadow8: 8px blur, 4px offset — command bars, tooltips
   - Shadow16: 16px blur, 8px offset — dialogs, flyouts
   - Dark theme uses 28% key + 24% ambient shadow opacity

3. **Semantic Status**: Fluent 2 uses cranberry (danger), green (success), orange (warning) with tint/shade variants

### Design Decisions

#### 1. Backwards Compatibility via Aliases

**Decision**: Keep all Phase 1 token names (BG_CANVAS, BG_PANEL, FG_PRIMARY, etc.) as aliases mapping to the new Fluent 2 tokens.

**Rationale**: Existing QSS rules in theme.py, editor_panel.py, source_picker.py reference the old names. Breaking those would require touching ~300 lines of QSS and widget code. Aliases preserve backward compat while adopting the new system.

#### 2. Explicit Layer Naming (not "subtle"/"medium")

**Decision**: Use `layer0`, `layer1`, `layer2`, `layer3`, `layer4` for shadow levels instead of custom descriptive names.

**Rationale**: Direct 1:1 mapping with Fluent 2 documentation (Shadow2 = layer1, Shadow4 = layer2, etc.) makes cross-referencing easier. Developers can look up Fluent 2 elevation spec and know exactly which token to use.

**Legacy support**: Kept `subtle` → `layer2` and `medium` → `layer3` aliases for existing `apply_shadow()` calls.

#### 3. Grey Ramp Abstraction

**Decision**: Expose semantic names (BG_LAYER_1, FG_1, STROKE_1) instead of raw `GREY_4`, `GREY_84` tokens.

**Rationale**: Fluent 2 web components use `colorNeutralBackground1`, not `grey[16]`. Our Python tokens follow the same semantic abstraction. Comments document the grey[N] mapping for reference.

**Trade-off**: Slightly less obvious which exact grey shade is used, but better aligns with Fluent 2's intent-based token system.

#### 4. No Visual Redesign

**Decision**: This is a *spec alignment* pass, not a UX overhaul. The theme should look nearly identical before/after.

**Rationale**: FollowCursor's dark theme was already ~70% Fluent-aligned. This change makes the palette *officially correct* without disrupting users or requiring new screenshots/docs. Visual changes can come later as a separate design iteration.

**Result**: Colors shifted slightly (e.g., BG_PANEL #131221 → #1f1f1f), but the overall vibe remains the same dark purple-accented theme.

#### 5. Material Effects Tokens (Stub)

**Decision**: Added `MATERIAL_OVERLAY_ALPHA = 0.92` and `MATERIAL_CARD_ALPHA = 0.98` tokens, but didn't implement acrylic/mica blur yet.

**Rationale**: Fluent 2 has a material system (acrylic for transient UI, mica for app backgrounds). The tokens are placeholders for Phase 4 when we add backdrop blur effects.

### Implementation Notes

- **All 375 tests pass** (3 updated, 5 new)
- **No breaking changes** — all existing QSS works via aliases
- **Better Windows 11 alignment** — colors now match native Windows apps
- **Foundation for Phase 4** — material effects (acrylic/mica) can layer on top

### References

- [Fluent 2 Color System](https://fluent2.microsoft.design/color)
- [Web Alias Color Tokens](https://fluent2.microsoft.design/color-tokens/)
- [Elevation Spec](https://fluent2.microsoft.design/elevation)

---
*Applied as of 2026-04-07T10:34:00Z*

## User Directive: PR Review Thread Resolution Comments

**Status:** Captured | **Date:** 2026-04-07T08:51:57Z | **By:** Ahmed Sabbour

When resolving PR review threads after fixing them, always add a reply comment explaining what was done to address the feedback before resolving the thread.

**Rationale:** User request — captured for team memory

---
*Captured as of 2026-04-07T08:51:57Z*

## User Directive: GitHub Pages Documentation Site

**Status:** Captured | **Date:** 2026-04-07T08:55:38Z | **By:** Ahmed Sabbour

Create a real GitHub Pages docs site. The squad-docs.yml workflow should build and deploy documentation to GitHub Pages, not just validate markdown.

**Rationale:** User request — captured for team memory

---
*Captured as of 2026-04-07T08:55:38Z*

## User Directive: Stop Using Git Worktrees

**Status:** Captured | **Date:** 2026-04-07T09:49:15Z | **By:** Ahmed Sabbour

Stop using git worktrees. Work on branches in the main repo checkout instead so changes are visible in the editor and runnable locally.

**Rationale:** User request — worktrees are confusing because files aren't visible in the editor and can't be run locally.

---
*Captured as of 2026-04-07T09:49:15Z*

## Decision: Batch-Install Focus Rings via findChildren

**Status:** Applied | **Date:** 2026-07-22 | **Author:** McManus (UI Dev)

Use `self.findChildren((QPushButton, QComboBox))` at the end of `EditorPanel.__init__` to batch-install focus rings on all interactive children. This auto-covers future additions without per-widget boilerplate.

For `main_window.py` and `title_bar.py`, explicit calls are used since the buttons are fewer and spread across builder methods.

### Trade-off

- **Pro**: Zero maintenance — any new QPushButton or QComboBox added to EditorPanel automatically gets a focus ring.
- **Con**: No opt-out mechanism for individual widgets. If a button needs a shadow instead, it would need the focus ring removed manually. Currently not a problem since all EditorPanel controls are interactive.

---
*Applied as of 2026-07-22*

## Squad Workflow Architecture (Fenster, PR #93)

**Status:** Complete | **Date:** 2026-07-18

### Decisions

1. **squad-release.yml creates tags only, does not build** — build.yml already handles `refs/tags/v*` releases. Duplicating the build/MSIX/release logic would create maintenance burden. squad-release.yml extracts the version from `version.py`, checks if the tag exists, and creates it. build.yml takes over from there.

2. **squad-ci.yml excludes PRs to main** — build.yml triggers on `pull_request: branches: [main]` with full build + artifacts. squad-ci.yml only covers PRs to dev/preview/insider with fast test-only runs to avoid redundant CI minutes.

3. **squad-docs.yml uses ubuntu-latest** — Only workflow not on `windows-latest`. Markdown validation doesn't need Windows, and ubuntu runners are faster and cheaper.

4. **Insider releases use `vX.Y.Z-insider.<short-sha>` tag format** — Distinguishes insider builds from stable releases and provides commit traceability without bumping version.py.

### Impact

These workflows complete the Squad branch promotion pipeline: dev → (squad-ci) → preview → (squad-preview validates) → main → (squad-release tags) → build.yml releases.

---
*Complete as of 2026-07-18*
