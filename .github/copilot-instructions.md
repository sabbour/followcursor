# FollowCursor — Copilot Agent Instructions

> Additional instruction files in `.github/instructions/` cover issue implementation conventions and release/versioning.

## Project Overview

FollowCursor is a **Windows screen recorder** with cinematic cursor-following zoom. It captures screen or window content, tracks mouse/keyboard/click activity, and exports polished MP4 or GIF files where the camera smoothly follows and zooms into the user's cursor movements.

**Target audience**: People creating tutorials, demos, and product walkthroughs.

## Tech Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| Language | Python 3.13 | Windows only |
| UI Framework | PySide6 (Qt 6) | Frameless window, custom dark theme |
| Screen Capture | dxcam (DXGI) + mss fallback | Hardware-accelerated monitor capture |
| Window Capture | Win32 PrintWindow (ctypes) | Per-window capture without bleed-through |
| Video Export | ffmpeg via imageio-ffmpeg | H.264 MP4 or GIF piped via stdin |
| Image Processing | OpenCV (cv2) + NumPy | Frame manipulation, thumbnails, cursor rendering |
| Input Tracking | Win32 Hooks (ctypes) | WH_MOUSE_LL, WH_KEYBOARD_LL via WINFUNCTYPE |
| Build | PyInstaller | Single-folder .exe distribution |
| Installer | MSIX | Signed Windows package via Azure Trusted Signing |
| CI | GitHub Actions | Windows runner, artifact upload |
| AI Features | azure-ai-inference | Optional AI zoom analysis, TTS voiceover via Azure AI Foundry |

## Repository Structure

```
followcursor/                    ← repo root
├── .github/
│   ├── copilot-instructions.md  ← This file (general context)
│   ├── instructions/            ← Domain-specific Copilot instructions
│   ├── prompts/                 ← Copilot prompt files (e.g. fix-errors)
│   └── workflows/build.yml     ← GitHub Actions CI
│                  auto-rebase.yml ← Auto-rebase open PRs on push to main
├── .vscode/                     ← VS Code config (launch, tasks, settings)
├── followcursor/                ← Python project root
│   ├── main.py                  ← Entry point
│   ├── requirements.txt         ← Python dependencies
│   ├── generate_msix_assets.py  ← Generate MSIX tile PNGs from app icon
│   ├── followcursor.ico         ← App icon
│   ├── msix/                    ← MSIX packaging files
│   │   ├── AppxManifest.xml     ← Package manifest template
│   │   └── Assets/              ← Generated tile PNGs (gitignored)
│   ├── scripts/                 ← Build & infra PowerShell scripts
│   │   ├── Build-App.ps1        ← PyInstaller build script
│   │   ├── Start-Dev.ps1        ← Dev setup & launch script
│   │   ├── Build-Msix.ps1      ← MSIX packaging + signing (local PFX or Azure)
│   │   └── Setup-AzureSigning.ps1 ← Provision Azure Trusted Signing resources
│   └── app/                     ← Application package
│       ├── main_window.py       ← Central coordinator
│       ├── models.py            ← Data classes
│       ├── screen_recorder.py   ← Capture engine (monitor + window modes)
│       ├── video_exporter.py    ← H.264 MP4 / GIF export with zoom/cursor/bezel
│       ├── compositor.py        ← QPainter compositing (frame + background)
│       ├── zoom_engine.py       ← Ease-out keyframe interpolation
│       ├── activity_analyzer.py ← Auto-zoom from activity bursts
│       ├── ai_service.py        ← AI zoom+pan analysis, TTS voiceover (Azure AI Foundry)
│       ├── mouse_tracker.py     ← QTimer cursor polling (60 Hz)
│       ├── keyboard_tracker.py  ← Win32 keyboard hook
│       ├── click_tracker.py     ← Win32 mouse click hook
│       ├── cursor_renderer.py   ← Arrow cursor rendering in export
│       ├── global_hotkeys.py    ← Ctrl+Shift+=/- zoom hotkeys
│       ├── window_utils.py      ← Win32 window enum & PrintWindow
│       ├── backgrounds.py       ← 84 background presets (solids + gradients + wavy patterns)
│       ├── frames.py            ← 5 device frame presets
│       ├── project_file.py      ← .fcproj ZIP save/load (with voiceover audio)
│       ├── icon.py              ← QPainter-generated app icon + .ico
│       ├── theme.py             ← DARK_THEME QSS stylesheet
│       └── widgets/
│           ├── title_bar.py
│           ├── source_picker.py ← Tabs: Screens / Windows
│           ├── preview_widget.py
│           ├── timeline_widget.py
│           ├── editor_panel.py
│           ├── countdown_overlay.py
│           ├── processing_overlay.py
│           └── recording_border.py
```

## Development Workflow

- **Run**: `scripts\Start-Dev.ps1` or press `F5` in VS Code
- **Build**: `scripts\Build-App.ps1` or press `Ctrl+Shift+B`
- **Test**: Execute the **Run Tests** VS Code task (do not run pytest manually in a terminal)
- **Debug**: F5 launches with debugpy attached
- VS Code automation terminals use `cmd.exe` (not WSL)

### Branching

All **features, bug fixes, and significant changes** must be developed on a dedicated branch (e.g. `fix/encoder-fallback`, `feat/gif-palette`). Create the branch before making changes, run the **Run Tests** task to verify, then merge back to `main` only after tests pass. Trivial documentation-only or comment-only edits may go directly on `main`.

### PR Scope

**Keep squad state changes separate from code changes** — except for `.squad/agents/*/history.md` files:

- **Allowed together:** `.squad/agents/*/history.md` may be committed in the same PR as code changes, because history files document the agent's understanding of the code it worked on and are contextual to the change being reviewed.
- **Must be separate:** `decisions.md`, `orchestration-log/`, `log/`, `ceremonies.md`, `team.md`, `routing.md`, and any other squad orchestration/state files must be kept in separate PRs and in their own dedicated commits, never bundled with code, documentation, or config changes.

### Parallel Work & Merge Conflicts

When multiple issues are being worked on simultaneously (e.g. by Copilot coding agent), **batch related issues** to avoid merge conflicts:

1. **Identify file overlap** — before starting a batch of issues, check which source files each issue will likely touch. Issues that modify the same files should be sequenced, not parallelized.
2. **Work in waves of 2–3** — start with 2–3 issues that target different areas of the codebase (e.g. one UI widget + one export change + one zoom engine fix). Merge those PRs, then start the next wave.
3. **File-area grouping** (as a guide):
   - **UI / widgets**: `main_window.py`, `widgets/`, `theme.py`, `compositor.py`, `backgrounds.py`, `frames.py`
   - **Capture / input**: `screen_recorder.py`, `window_utils.py`, `mouse_tracker.py`, `keyboard_tracker.py`, `click_tracker.py`
   - **Export**: `video_exporter.py`, `cursor_renderer.py`, `utils.py`
   - **Zoom / timeline**: `zoom_engine.py`, `activity_analyzer.py`, `ai_service.py`, `timeline_widget.py`, `editor_panel.py`
   - **Data / project**: `models.py`, `project_file.py`
   - **Docs / CI**: `docs/`, `.github/`, `README.md`
4. **Auto-rebase** — a GitHub Actions workflow (`.github/workflows/auto-rebase.yml`) automatically rebases all open PRs whenever `main` is updated. PRs labeled `no-rebase` are excluded.

### Test Suite

- **Framework**: pytest (configured via `followcursor/pytest.ini`)
- **Location**: `followcursor/tests/` — tests target the pure-logic layer (no Qt dependency)
- **Modules tested**: models, zoom_engine, activity_analyzer, utils, frames, backgrounds, project_file, ai_service
- **CI**: tests run automatically before the PyInstaller build in GitHub Actions
- **Convention**: one `test_<module>.py` per source module; shared fixtures in `conftest.py`

## Coding Conventions

- All UI is built with PySide6 widgets (no QML, no Qt Designer .ui files)
- Dark theme via QSS in `theme.py`, not palette manipulation (palette is minimal base only)
- Signals/slots for all inter-component communication
- Background threads for: recording, export, input hooks, thumbnail generation
- QSettings("FollowCursor", "FollowCursor") for persisted settings
- Type hints on all function signatures
- Docstrings on classes and complex methods
- **Logging** via Python's `logging` module — no bare `print()`. Each module uses `logger = logging.getLogger(__name__)`. `logging.basicConfig()` is configured in `main.py` with format `"%(name)s | %(levelname)s | %(message)s"` at level `INFO`
- **Error log file**: A `RotatingFileHandler` in `main.py` writes ERROR+ entries to `%LOCALAPPDATA%/FollowCursor/error.log` (2 MB, 3 backups). Entries include timestamp, module, file path, line number, function name, and full traceback. Use the `/fix-errors` prompt to diagnose and fix logged errors.

## Documentation Maintenance

Whenever a feature is **added, changed, or removed**, update the relevant documentation:

1. **`docs/USER_GUIDE.md`** — User-facing feature descriptions, tables, and shortcuts
2. **`docs/QUICKSTART.md`** — Getting-started workflow changes
3. **`docs/ARCHITECTURE.md`** — System design, data flow, or component changes
4. **`docs/CONTRIBUTING.md`** — Dev setup, coding conventions, or release process changes
5. **`followcursor/README.md`** — Features, architecture, shortcuts, or project structure changes
6. **`.github/copilot-instructions.md`** and **`.github/instructions/`** — Architecture, tech stack, repo structure, or convention changes

Do **not** skip documentation updates — they are part of completing any feature or bug fix.

## Common Pitfalls

1. **Never** use `source` or `bash` commands for Windows Python — use `.venv\Scripts\python.exe` directly
2. **Never** add `SetProcessDpiAwareness` — Qt handles it
3. **Never** use `CFUNCTYPE` for Win32 hook callbacks — use `WINFUNCTYPE`. Hook callbacks must have explicit `argtypes` and `restype` to prevent integer overflow on 64-bit pointers
4. **Never** use trademarked device names (Surface, MacBook) in frame presets
5. **Never** run compositor during recording — use blur overlay instead
6. Catch both `BrokenPipeError` and `OSError` on ffmpeg pipe writes — Windows raises `OSError(22)` instead of `BrokenPipeError`
7. `closeEvent` uses `os._exit(0)` for clean shutdown — prevents Qt cleanup hangs with native hooks
8. `.github/` folder lives at **repo root**, not inside `followcursor/`
9. `.gitignore` lives at **repo root**
10. VS Code config (`.vscode/`) lives at **repo root**
11. Python project files live inside `followcursor/` subfolder
