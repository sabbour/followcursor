# Work Routing

How to decide who handles what.

## Work Type → Agent

| Work Type | Agent | Examples |
|-----------|-------|----------|
| Screen/window capture | Fenster | dxcam, WGC, PrintWindow, recording pipeline |
| Video export | Fenster | ffmpeg pipe, H.264, GIF, cursor rendering |
| Zoom engine | Fenster | keyframe interpolation, ease-out, activity analysis |
| Input tracking | Fenster | mouse hooks, keyboard hooks, click tracker |
| Project file | Fenster | .fcproj save/load, ZIP bundle |
| UI widgets | McManus | PySide6 widgets, timeline, preview, editor panel |
| Theme & visual | McManus | QSS, tokens, Fluent 2 components, dark theme |
| Documentation | McManus | User guide, README, QUICKSTART, MkDocs site |
| AI features | Fenster | ai_service.py, Azure AI Foundry, TTS voiceover |
| Testing | Hockney | pytest, test coverage, edge cases |
| Bug investigation | Hockney | repro steps, root cause, fix verification |
| Architecture decisions | Keaton | design trade-offs, scope, system design |
| Issue triage | Ralph | squad label routing, heartbeat, PR monitoring |
| Session logging | Scribe | Automatic — never needs routing |

## Module Ownership

| Module | Primary | Secondary |
|--------|---------|-----------|
| `followcursor/app/screen_recorder.py` | Fenster | — |
| `followcursor/app/video_exporter.py` | Fenster | — |
| `followcursor/app/zoom_engine.py` | Fenster | — |
| `followcursor/app/activity_analyzer.py` | Fenster | — |
| `followcursor/app/ai_service.py` | Fenster | — |
| `followcursor/app/mouse_tracker.py` | Fenster | — |
| `followcursor/app/keyboard_tracker.py` | Fenster | — |
| `followcursor/app/click_tracker.py` | Fenster | — |
| `followcursor/app/cursor_renderer.py` | Fenster | — |
| `followcursor/app/window_utils.py` | Fenster | — |
| `followcursor/app/project_file.py` | Fenster | — |
| `followcursor/app/models.py` | Fenster | McManus |
| `followcursor/app/main_window.py` | McManus | Fenster |
| `followcursor/app/widgets/` | McManus | — |
| `followcursor/app/theme.py` | McManus | — |
| `followcursor/app/tokens.py` | McManus | — |
| `followcursor/app/backgrounds.py` | McManus | — |
| `followcursor/app/frames.py` | McManus | — |
| `followcursor/app/compositor.py` | McManus | Fenster |
| `followcursor/app/icon_loader.py` | McManus | — |
| `followcursor/app/fluent_effects.py` | McManus | — |
| `followcursor/app/global_hotkeys.py` | Fenster | — |
| `followcursor/tests/` | Hockney | — |
| `docs/` | McManus | — |
| `README.md` | McManus | — |
| `.github/workflows/` | Keaton | Fenster |
| `followcursor/scripts/` | Fenster | — |



| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage: analyze issue, assign `squad:{member}` label | Lead |
| `squad:{name}` | Pick up issue and complete the work | Named member |

### How Issue Assignment Works

1. When a GitHub issue gets the `squad` label, the **Lead** triages it — analyzing content, assigning the right `squad:{member}` label, and commenting with triage notes.
2. When a `squad:{member}` label is applied, that member picks up the issue in their next session.
3. Members can reassign by removing their label and adding another member's label.
4. The `squad` label is the "inbox" — untriaged issues waiting for Lead review.

## Rules

1. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work.
2. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
3. **Quick facts → coordinator answers directly.** Don't spawn an agent for "what port does the server run on?"
4. **When two agents could handle it**, pick the one whose domain is the primary concern.
5. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel as `mode: "background"`.
6. **Anticipate downstream work.** If a feature is being built, spawn the tester to write test cases from requirements simultaneously.
7. **Issue-labeled work** — when a `squad:{member}` label is applied to an issue, route to that member. The Lead handles all `squad` (base label) triage.
