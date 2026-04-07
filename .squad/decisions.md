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
