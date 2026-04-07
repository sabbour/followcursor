# Team Decisions

## Directives

### 2026-04-07T08:13:04Z: No Force Merge

**By:** Ahmed Sabbour (via Copilot)

Never force merge PRs just to get things done. Always wait for CI builds to pass AND address all pending review comments, especially those from Copilot code review, before merging.

### 2026-04-07T08:15:00Z: Wait for Copilot Review

**By:** Ahmed Sabbour (via Copilot)

If Copilot is requested as a reviewer on a PR, wait for Copilot's review to be completed and address any comments before merging.

## Applied Decisions

### 2026-04-07: Fluent 2 Phase 2 — Visual Polish Decisions (McManus)

**Status:** Applied | **Branch:** `feat/fluent2-phase2`

#### Context

Phase 2 adds the visual polish layer on top of the Phase 1 token system — shadows, hover animations, focus indicators, and scrollbar refinements.

#### Decisions

1. **fluent_effects.py as the effects module** — all visual effect helpers (shadows, hover animations, focus rings) live in `app/fluent_effects.py`. Other modules import helpers from here rather than implementing their own QGraphicsDropShadowEffect or QPropertyAnimation code.

2. **Event filter pattern over subclassing** — hover animations and focus rings use QObject event filters (`HoverAnimationFilter`, `FocusRingFilter`) attached via `installEventFilter()`. This avoids subclassing QPushButton, QFrame, etc. for every effect and keeps widget code clean.

3. **Shadow vs focus ring exclusivity** — `QGraphicsDropShadowEffect` allows only one effect per widget. Shadows go on passive surfaces (cards, dialogs); focus rings go on interactive controls (buttons, inputs). Never apply both to the same widget.

4. **Focus indicators via QSS border, not outline** — Qt's QSS `outline` property is unreliable. Focus indicators use `border: 2px solid {BRAND}` on `:focus` pseudo-state instead. This works consistently across all standard Qt widgets.

5. **Scrollbar hover expansion in pure QSS** — the scrollbar expands from 6px to 12px on hover using `:hover` pseudo-state width/height changes. No animation needed — Qt handles the transition. Both vertical and horizontal scrollbar styling added.

6. **Hardcoded hex migration scope** — editor_panel.py had ~30 hardcoded hex colors. All were migrated to token references in this phase. Future widgets should import from `tokens` — never hardcode `#8b5cf6` or similar.

#### Impact

- New module: `followcursor/app/fluent_effects.py`
- New tests: `followcursor/tests/test_fluent_effects.py` (13 tests)
- Modified: tokens.py, theme.py, source_picker.py, editor_panel.py
- All 347 tests pass
