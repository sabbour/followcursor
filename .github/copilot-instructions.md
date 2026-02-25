# FollowCursor — Copilot Agent Instructions

## Project Overview

FollowCursor is a **Windows screen recorder** with cinematic cursor-following zoom. It captures screen or window content, tracks mouse/keyboard/click activity, and exports polished MP4 videos where the camera smoothly follows and zooms into the user's cursor movements.

**Target audience**: People creating tutorials, demos, and product walkthroughs.

## Tech Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| Language | Python 3.13 | Windows only |
| UI Framework | PySide6 (Qt 6) | Frameless window, custom dark theme |
| Screen Capture | dxcam (DXGI) + mss fallback | Hardware-accelerated monitor capture |
| Window Capture | Win32 PrintWindow (ctypes) | Per-window capture without bleed-through |
| Video Export | ffmpeg via imageio-ffmpeg | H.264 MP4 piped via stdin; auto-detects HW encoders (NVENC, QuickSync, AMF) with libx264 fallback |
| Image Processing | OpenCV (cv2) + NumPy | Frame manipulation, thumbnails, cursor rendering |
| Input Tracking | Win32 Hooks (ctypes) | WH_MOUSE_LL, WH_KEYBOARD_LL via WINFUNCTYPE |
| Build | PyInstaller | Single-folder .exe distribution |
| CI | GitHub Actions | Windows runner, artifact upload |

## Repository Structure

```
followcursor/                    ← repo root
├── .github/workflows/build.yml  ← GitHub Actions CI
├── .vscode/                     ← VS Code config (launch, tasks, settings)
├── followcursor/                ← Python project root
│   ├── main.py                  ← Entry point
│   ├── requirements.txt         ← Python dependencies
│   ├── build.bat                ← PyInstaller build script
│   ├── dev.bat                  ← Dev setup & launch script
│   ├── followcursor.ico         ← App icon
│   └── app/                     ← Application package
│       ├── main_window.py       ← Central coordinator (~1000 lines)
│       ├── models.py            ← Data classes
│       ├── screen_recorder.py   ← Capture engine (monitor + window modes)
│       ├── video_exporter.py    ← H.264 MP4 export with zoom/cursor/bezel
│       ├── compositor.py        ← QPainter compositing (frame + background)
│       ├── zoom_engine.py       ← Ease-out keyframe interpolation
│       ├── activity_analyzer.py ← Auto-zoom from activity bursts
│       ├── mouse_tracker.py     ← QTimer cursor polling (60 Hz)
│       ├── keyboard_tracker.py  ← Win32 keyboard hook
│       ├── click_tracker.py     ← Win32 mouse click hook
│       ├── cursor_renderer.py   ← Arrow cursor rendering in export
│       ├── global_hotkeys.py    ← Ctrl+Shift+=/- zoom hotkeys
│       ├── window_utils.py      ← Win32 window enum & PrintWindow
│       ├── backgrounds.py       ← 84 background presets (solids + gradients + wavy patterns)
│       ├── frames.py            ← 5 device frame presets
│       ├── project_file.py      ← .fcproj ZIP save/load
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

## Key Architecture Decisions

### DPI Awareness
- **Do NOT** call `SetProcessDpiAwareness` manually — PySide6 already sets `PER_MONITOR_DPI_AWARE_V2`
- Window capture via `PrintWindow` returns physical pixels; do not apply DPI scale factors

### Win32 Hooks (ctypes)
- Mouse and keyboard hooks use `WINFUNCTYPE` (not `CFUNCTYPE`) for 64-bit Windows compatibility
- Hook callbacks must have explicit `argtypes` and `restype` to prevent integer overflow on 64-bit pointers
- `CallNextHookEx` needs proper argument types defined

### Taskbar Close
- `_WinCloseFilter` (QAbstractNativeEventFilter) is installed on QApplication to intercept `WM_CLOSE`
- `closeEvent` calls `os._exit(0)` for clean shutdown (prevents Qt cleanup hangs with native hooks)

### Recording Performance
- During recording, the preview widget shows a **static blurred snapshot** (not live compositor output)
- `screen_recorder.py` skips emitting preview frames during recording to reduce CPU load
- The compositor pipeline only runs during playback/editing

### Video Export Pipeline
- Frames are piped to ffmpeg via stdin (not written to temp files)
- GPU-accelerated encoding: `detect_available_encoders()` in `utils.py` probes NVENC / QuickSync / AMF at startup; `best_hw_encoder()` picks the fastest available, falling back to `libx264`
- `ENCODER_PROFILES` dict maps each encoder ID to codec + quality args (tuned to approximate CRF 18)
- `build_encoder_args(encoder_id)` returns the ffmpeg arg list for the selected encoder
- Encoder choice is persisted via QSettings and exposed in the editor panel's ⚙ settings menu as a **Video encoder** submenu
- `VideoExporter.export()` and `_run()` accept an `encoder_id` parameter; the ffmpeg command is built dynamically via `build_encoder_args()`
- **Encoder fallback chain (two-phase)**: (1) immediate check — if ffmpeg exits within 100ms, try the next available HW encoder in priority order (NVENC → QuickSync → AMF), falling back to `libx264` only after all HW encoders are exhausted; (2) mid-stream retry — if the HW encoder fails partway through, restart the full encode walking the same fallback chain. `VideoExporter` emits `status = Signal(str)` and `MainWindow._on_export_status()` updates the status bar on each fallback attempt
- **Pipe error handling**: both `BrokenPipeError` and `OSError` are caught on pipe writes (Windows raises `OSError(22)` instead of `BrokenPipeError`)
- Status bar shows active encoder display name during export (e.g. "Encoding with NVIDIA NVENC…") and updates on each fallback attempt (e.g. "Encoder fallback: trying Intel QuickSync…", then "Encoder fallback: using libx264…")
- **Zoom behavior is conditional on frame preset**:
  - **No Frame**: zoom/pan applies only to the video content inside the screen area — background stays static. Cursor and click overlays use virtual screen-rect mapping with clip rect when zoomed.
  - **Device frame (any bezel)**: zoom/pan moves the device (frame + video) while the background stays static — like physically bringing a device closer and moving it around. The background gradient/pattern is always visible and never zooms.
- Export renders each frame with zoom, cursor overlay, device bezel, and background

### Zoom System
- `ZoomKeyframe` has: time_s, target_x, target_y, scale, duration
- **Ease-out** easing (`1 - (1-t)⁵`) for all zoom and pan transitions — quintic curve gives very pronounced deceleration, ~80% of movement in the first 40% of duration. Old `smooth_step` name kept as alias for backward compatibility
- Default transition duration: 600ms
- **Anticipation**: zoom-in and pan transitions complete `ANTICIPATION_MS` (200ms) *before* the activity starts, so the viewer sees the trigger from the beginning
- Activity analyzer generates keyframes from mouse speed bursts, typing clusters, and click events
- Spatial-aware clustering merges same-type peaks (clicks, typing) that are close in screen position
- **Pan-while-zoomed chains**: consecutive clusters within `PAN_MERGE_GAP_MS` (3000ms) are grouped — camera zooms in at the first cluster, pans smoothly to each subsequent cluster while staying zoomed, then zooms out only after the last cluster. Chains are capped at `MAX_CHAIN_LENGTH = 4` clusters. Pan duration scales with distance (`PAN_TRANSITION_MS = 400`–`PAN_TRANSITION_MAX_MS = 700` ms)
- Dampened panning: `_dampen_pan()` accepts `from_x`/`from_y` to compute the minimal shift from the current viewport position (not always from center). Viewport is clamped so it never flies off the source edge.
- Manual keyframes via right-click on timeline or editor panel
- **Undo/redo**: `ZoomEngine` has snapshot-based undo/redo (deep-copy, MAX_UNDO=50). `push_undo()` called before every mutation. Drag operations debounced via `_drag_undo_pushed` flag.
- **Dirty tracking**: `_unsaved_changes` flag set by `_mark_dirty()` after every mutation; cleared on save

### Trimming
- Timeline has draggable trim handles at both edges (yellow bars, dimmed overlay for trimmed regions)
- `RecordingSession` stores `trim_start_ms` and `trim_end_ms` (persisted in .fcproj)
- `VideoExporter` skips frames outside trim range during export
- 500ms minimum constraint on trimmed duration

### Project Path & Title Bar
- `_project_path` tracks the current .fcproj file path; Ctrl+S re-saves without dialog
- `TitleBar.set_title(name, unsaved)` updates the logo label to show project name + ● indicator
- Close confirmation dialog (Save / Don’t Save / Cancel) when `_unsaved_changes` is True

### Processing Overlay
- `ProcessingOverlay` widget (full-window, pulsing banner) shown during long-running operations
- Reusable: `show_overlay(title, subtitle)` accepts configurable text — used for both recording finalization ("Processing…") and project loading ("Loading project…")
- Project loading runs on a background `_LoadProjectWorker(QThread)` so the UI stays responsive during ZIP extraction
- Replaces the subtle status-bar text with a prominent visual indicator

### Preview Canvas Sizing
- The compositor's `compose_scene` is called with `(canvas_w, canvas_h)` instead of full widget dimensions; the painter is translated and clipped to the canvas rect
- **Auto (source)**: canvas is letterboxed/pillarboxed to match the source video's native aspect ratio
- **Non-auto presets** (e.g., 1:1, 4:3): the device frame is fitted and centered within the target aspect ratio, giving an accurate preview of the export result
- Replaces the previous scrim-overlay approach (semi-transparent dark overlay drawn over margin areas)

### Error Resilience
- `sys.excepthook` is set in `main.py` to log unhandled exceptions via `logging`
- `_do_start_recording()`, `_stop_recording()`, `_on_finalize_done()` are wrapped in `try/except` with `logger.exception()`
- Win32 hook callbacks in `click_tracker.py` and `keyboard_tracker.py` have `try/except` guards
- On failure, the UI is restored to a usable state (buttons re-shown, overlays hidden)

### Frame Presets
- Names must be **generic** (no trademarked device names)
- Current: Wide Bezel, Slim Bezel, Thin Border, Shadow Only, No Frame

### Build Optimization
- PyInstaller excludes 40+ unused PySide6 modules (QtWebEngine, Qt3D, QtMultimedia, QtQml, etc.)
- Only QtCore, QtGui, QtWidgets, QtSvg are needed
- Also excludes tkinter, unittest, email, http, xml, pydoc

## Development Workflow

- **Run**: `dev.bat` or press `F5` in VS Code
- **Build**: `build.bat` or press `Ctrl+Shift+B`
- **Debug**: F5 launches with debugpy attached
- VS Code automation terminals use `cmd.exe` (not WSL) — configured via `terminal.integrated.automationProfile.windows`

## Coding Conventions

- All UI is built with PySide6 widgets (no QML, no Qt Designer .ui files)
- Dark theme via QSS in `theme.py`, not palette manipulation (palette is minimal base only)
- Signals/slots for all inter-component communication
- Background threads for: recording, export, input hooks, thumbnail generation
- QSettings("FollowCursor", "FollowCursor") for persisting: window geometry, last export dir, last project dir
- Type hints on all function signatures
- Docstrings on classes and complex methods
- **Logging** via Python's `logging` module — no bare `print()` calls. Each module uses `logger = logging.getLogger(__name__)`. `logging.basicConfig()` is configured in `main.py` with format `"%(name)s | %(levelname)s | %(message)s"` at level `INFO`

## Documentation Maintenance

Whenever a feature is **added, changed, or removed**, you **must** update the relevant documentation:

1. **`docs/USER_GUIDE.md`** — Update the user-facing feature descriptions, tables, and shortcuts
2. **`docs/QUICKSTART.md`** — Update if the change affects the getting-started workflow
3. **`docs/ARCHITECTURE.md`** — Update if the change affects system design, data flow, or component responsibilities
4. **`docs/CONTRIBUTING.md`** — Update if the change affects dev setup, coding conventions, or release process
5. **`followcursor/README.md`** — Update the features list, architecture table, shortcuts table, or project structure if they are affected
6. **`.github/copilot-instructions.md`** — Update if the change affects architecture decisions, tech stack, repo structure, or coding conventions

Do **not** skip documentation updates — they are part of completing any feature or bug fix.

## Common Pitfalls

1. **Never** use `source` or `bash` commands for Windows Python — always use `.venv\Scripts\python.exe` directly
2. **Never** add `SetProcessDpiAwareness` — Qt handles it
3. **Never** use `CFUNCTYPE` for Win32 hook callbacks — use `WINFUNCTYPE`
4. **Never** use trademarked device names (Surface, MacBook) in frame presets
5. **Never** run compositor during recording — use blur overlay instead
6. The `.github/` folder lives at **repo root**, not inside `followcursor/`
7. The `.gitignore` lives at **repo root**
8. VS Code config (`.vscode/`) lives at **repo root**
9. Python project files live inside `followcursor/` subfolder
