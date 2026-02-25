# Contributing to FollowCursor

Thanks for your interest in contributing! This guide covers everything you need to set up a development environment and submit changes.

---

## Development Setup

### Prerequisites

- **Windows 10 (build 1903+) or Windows 11**
- **Python 3.10+** — [Download](https://www.python.org/downloads/) (check "Add to PATH")
- **Git** — [Download](https://git-scm.com/downloads)
- **VS Code** (recommended) — [Download](https://code.visualstudio.com/)

### Clone & install

```bat
git clone https://github.com/your-org/followcursor.git
cd followcursor/followcursor
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Or simply run `dev.bat` to do all of this and launch the app.

### VS Code integration

The repo includes VS Code configuration in `.vscode/`:

- **F5** — Launch with debugger (debugpy attached)
- **Ctrl+Shift+B** — Build standalone `.exe` via PyInstaller
- Automation terminals use `cmd.exe` (not WSL) — configured via `terminal.integrated.automationProfile.windows`

---

## Repository Layout

```text
followcursor/              ← repo root (.git, .github, .vscode live here)
├── .github/workflows/     ← CI pipeline
├── .vscode/               ← VS Code tasks, launch, settings
├── docs/                  ← Documentation
│   ├── QUICKSTART.md
│   ├── ARCHITECTURE.md
│   └── CONTRIBUTING.md
└── followcursor/          ← Python project root
    ├── main.py            ← Entry point
    ├── requirements.txt
    ├── build.bat
    ├── dev.bat
    └── app/               ← Application package
        ├── version.py     ← Single source of truth for version
        ├── models.py
        ├── ...
        └── widgets/
```

> **Note:** The `.github/` and `.vscode/` folders live at **repo root**, not inside `followcursor/`. The Python project files live inside the `followcursor/` subfolder.

---

## Coding Conventions

### Python

- **Type hints** on all function signatures
- **Docstrings** on classes and complex methods
- Use `from __future__ import annotations` is not needed — Python 3.10+ union syntax (`X | None`) is used directly

### Qt / PySide6

- All UI built with **PySide6 widgets** — no QML, no Qt Designer `.ui` files
- Dark theme via **QSS** in `theme.py` — not palette manipulation
- **Signals/slots** for all inter-component communication
- Use `setPixelSize()` for fonts — never `setPointSize()` (avoids DPI issues)

### Naming

- Snake_case for functions and variables
- PascalCase for classes
- Private methods prefixed with `_`
- Constants in UPPER_SNAKE_CASE

### Threading

- Background threads for: recording, export, input hooks, thumbnail generation
- Never access Qt widgets from background threads — use signals to communicate back to the main thread

---

## Common Pitfalls

1. **Never** use `source` or `bash` commands for Windows Python — always use `.venv\Scripts\python.exe` directly
2. **Never** add `SetProcessDpiAwareness` — PySide6 already sets `PER_MONITOR_DPI_AWARE_V2`
3. **Never** use `CFUNCTYPE` for Win32 hook callbacks — use `WINFUNCTYPE` for 64-bit compatibility
4. **Never** use trademarked device names (Surface, MacBook) in frame presets
5. **Never** run the compositor during recording — use blur overlay instead
6. **Never** import heavy modules at the top of widget files if they're only used in specific methods — use deferred imports

---

## Making Changes

### Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Verify all files compile:

   ```bat
   .venv\Scripts\python.exe -c "import py_compile, pathlib; [py_compile.compile(str(f), doraise=True) for f in pathlib.Path('.').rglob('*.py') if '.venv' not in str(f)]"
   ```

4. Run the test suite:

   ```bat
   .venv\Scripts\python.exe -m pytest tests/ -v
   ```

5. Test manually — launch the app and verify your changes work
6. Commit with a descriptive message
7. Push and open a Pull Request

### Adding a new widget

1. Create `app/widgets/your_widget.py`
2. Use `QWidget` and set an `objectName` for QSS styling
3. Define signals for outbound communication
4. Wire it up in `MainWindow.__init__`
5. Add QSS rules in `theme.py` if needed

### Adding a background preset

Edit `app/backgrounds.py` — add a new `BackgroundPreset` to the `PRESETS` list. The editor panel grid auto-generates buttons for all presets.

### Adding a frame preset

Edit `app/frames.py` — add a new `FramePreset` to the `FRAME_PRESETS` list. Use generic names only.

---

## Versioning

FollowCursor uses [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):

- **MAJOR** — breaking changes to project file format or CLI
- **MINOR** — new features (new background presets, zoom modes, etc.)
- **PATCH** — bug fixes

The version lives in `followcursor/app/version.py`:

```python
__version__ = "0.1.0"
```

### Releasing

1. Update `__version__` in `app/version.py`
2. Commit: `git commit -am "Bump version to 0.2.0"`
3. Tag: `git tag v0.2.0`
4. Push: `git push origin main --tags`
5. GitHub Actions builds and creates a Release automatically

---

## Architecture Overview

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed walkthrough of:

- Data flow from recording → editing → export
- Zoom engine interpolation (smootherstep easing)
- Activity analyzer signal detection
- Compositor pipeline (QPainter for preview, NumPy for export)
- Threading model
- UI widget hierarchy

---

## Dependencies

| Package | Version | Purpose |
| ------- | ------- | ------- |
| PySide6 | ≥ 6.6.0 | Qt 6 GUI framework |
| mss | ≥ 9.0.0 | GDI fallback screen capture |
| opencv-python | ≥ 4.9.0 | Video decode/encode, image processing |
| numpy | ≥ 1.26.0 | Array operations for frame manipulation |
| imageio-ffmpeg | ≥ 0.5.1 | Bundled ffmpeg binary |
| windows-capture | ≥ 1.5.0 | Windows Graphics Capture API bindings |

To add a dependency:

1. `pip install package-name`
2. Add it to `requirements.txt` with a minimum version
3. If it's heavy and not needed at import time, use a deferred import

---

## Build & CI

### Local build

```bat
build.bat
```

Produces `dist/FollowCursor/FollowCursor.exe` — a single-folder PyInstaller distribution.

### CI pipeline

GitHub Actions runs on every push/PR to `main`:

1. Extracts version from `app/version.py`
2. Installs dependencies
3. Builds with PyInstaller (same exclude list as `build.bat`)
4. Uploads versioned artifact
5. Creates GitHub Release on `v*` tags

---

## Questions?

Open an issue on GitHub or check the [Quickstart Guide](QUICKSTART.md) for usage help.
