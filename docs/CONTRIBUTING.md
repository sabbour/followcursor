# Contributing Guide

Thanks for your interest in contributing! This guide covers everything you need to set up a development environment and submit changes.

---

## Development Setup

### Prerequisites

- **Windows 10 (build 1903+) or Windows 11**
- **Python 3.13** — [Download](https://www.python.org/downloads/) (check "Add to PATH")
- **Git** — [Download](https://git-scm.com/downloads)
- **VS Code** (recommended) — [Download](https://code.visualstudio.com/)

!!! warning "ARM64 Windows"
    Install the **x64** edition of Python, not ARM64. Many dependencies (OpenCV, windows-capture) don't have ARM64 wheels. x64 Python runs fine via emulation.

### Clone & Install

```powershell
git clone https://github.com/sabbour/followcursor.git
cd followcursor/followcursor
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Or run `.\scripts\Start-Dev.ps1` to do all of this and launch the app.

### VS Code Integration

The repo includes VS Code configuration in `.vscode/`:

- **F5** — Launch with debugger (debugpy attached)
- **Ctrl+Shift+B** — Build standalone `.exe` via PyInstaller
- Automation terminals use `cmd.exe` (not WSL)

---

## Repository Layout

```
followcursor/              <-- repo root (.git, .github, .vscode)
|-- .github/workflows/     <-- CI pipeline
|-- .vscode/               <-- VS Code tasks, launch, settings
|-- docs/                  <-- Documentation (mkdocs-material site)
+-- followcursor/          <-- Python project root
    |-- main.py            <-- Entry point
    |-- requirements.txt
    |-- pytest.ini
    |-- scripts/           <-- Build & infra PowerShell scripts
    |-- tests/             <-- Unit tests (pytest)
    +-- app/               <-- Application package
        |-- version.py     <-- Single source of truth for version
        |-- models.py      <-- Data classes
        |-- tokens.py      <-- Fluent 2 design tokens
        |-- theme.py       <-- QSS dark theme
        +-- widgets/       <-- UI widgets
```

!!! note
    `.github/` and `.vscode/` live at **repo root**, not inside `followcursor/`. Python project files live inside the `followcursor/` subfolder.

---

## Coding Conventions

### Python

- **Type hints** on all function signatures
- **Docstrings** on classes and complex methods
- Python 3.10+ union syntax (`X | None`) used directly
- **Logging** via `logging` module — no bare `print()`. Each module: `logger = logging.getLogger(__name__)`

### Qt / PySide6

- All UI built with **PySide6 widgets** — no QML, no Qt Designer `.ui` files
- Dark theme via **QSS** in `theme.py` — not palette manipulation
- **Signals/slots** for all inter-component communication
- Use `setPixelSize()` for fonts — never `setPointSize()` (avoids DPI issues)

### Design Tokens

All colors, spacing, radii, and typography values come from `app/tokens.py`. Import as `from . import tokens as T` and reference token constants instead of hardcoding hex values or pixel sizes.

### Naming

- `snake_case` for functions and variables
- `PascalCase` for classes
- Private methods prefixed with `_`
- Constants in `UPPER_SNAKE_CASE`

### Threading

- Background threads for: recording, export, input hooks, thumbnail generation
- Never access Qt widgets from background threads — use signals
- Win32 hooks use `WINFUNCTYPE` (not `CFUNCTYPE`) for 64-bit compatibility

---

## Testing

### Test Suite

- **Framework:** pytest (configured via `followcursor/pytest.ini`)
- **Location:** `followcursor/tests/` — one `test_<module>.py` per source module
- **Current count:** 359 tests
- **Scope:** Pure-logic layer (no Qt dependency in tests)

### Modules Tested

models, zoom_engine, activity_analyzer, utils, frames, backgrounds, project_file, ai_service, fluent_effects

### Running Tests

Execute the **Run Tests** VS Code task (`Ctrl+Shift+P` > Tasks: Run Task > Run Tests).

!!! warning
    Do **not** run pytest manually in a terminal — use the VS Code task to ensure the correct environment and working directory.

### Writing Tests

- Place tests in `followcursor/tests/test_<module>.py`
- Use shared fixtures from `conftest.py`
- Test data models, serialization roundtrips, algorithms, and edge cases
- Tests must not depend on Qt (no widget instantiation)

---

## Security Conventions

### Credential Storage

- **Use Windows DPAPI** — encrypt credentials before storing in Windows Registry
- **Decrypt on-demand** — decrypt only when the credential is needed
- **Never log credentials** — sanitize debug output
- See `app/credentials.py` for the encrypt/decrypt implementation

### Temporary File Cleanup

- Delete temp files immediately when no longer needed
- Use unique filenames (`tempfile.NamedTemporaryFile()` or randomized names)
- Track extraction directories and clean up in `closeEvent()`
- Wrap deletion in try/except for file-in-use errors

---

## Common Pitfalls

1. **Never** use `source` or `bash` commands for Windows Python — use `.venv\Scripts\python.exe`
2. **Never** add `SetProcessDpiAwareness` — PySide6 already sets `PER_MONITOR_DPI_AWARE_V2`
3. **Never** use `CFUNCTYPE` for Win32 hook callbacks — use `WINFUNCTYPE`
4. **Never** use trademarked device names in frame presets
5. **Never** run the compositor during recording — use blur overlay instead
6. **Never** import heavy modules at top of widget files — use deferred imports
7. Catch both `BrokenPipeError` and `OSError` on ffmpeg pipe writes (Windows raises `OSError(22)`)
8. `closeEvent` uses `os._exit(0)` for clean shutdown

---

## Making Changes

### Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run the **Run Tests** VS Code task — all tests must pass
4. Test manually — launch the app and verify
5. Commit with a descriptive message
6. Push and open a Pull Request

### Branching Strategy

All features, bug fixes, and significant changes must be developed on a **dedicated branch** (e.g. `fix/encoder-fallback`, `feat/gif-palette`). Trivial documentation-only edits may go directly on `main`.

An **auto-rebase** workflow (`.github/workflows/auto-rebase.yml`) automatically rebases all open PRs whenever `main` is updated. PRs labeled `no-rebase` are excluded.

### Adding a New Widget

1. Create `app/widgets/your_widget.py`
2. Use `QWidget` with an `objectName` for QSS styling
3. Define signals for outbound communication
4. Wire it up in `MainWindow.__init__`
5. Add QSS rules in `theme.py` using tokens from `tokens.py`

### Adding a Background Preset

Edit `app/backgrounds.py` — add a `BackgroundPreset` to the `PRESETS` list. The editor panel grid auto-generates buttons.

### Adding a Frame Preset

Edit `app/frames.py` — add a `FramePreset` to `FRAME_PRESETS`. Use generic names only (no trademarks).

---

## Versioning

FollowCursor uses [Semantic Versioning](https://semver.org/) (MAJOR.MINOR.PATCH):

| Bump | When |
| ---- | ---- |
| **MAJOR** | Breaking changes to project file format, CLI, or public API |
| **MINOR** | New features, new export formats, new UI panels |
| **PATCH** | Bug fixes, performance improvements, documentation fixes |

The version lives in `followcursor/app/version.py`:

```python
__version__ = "0.8.0"
```

### Releasing

1. Update `__version__` in `app/version.py`
2. Add a new section to `CHANGELOG.md` with today's date
3. Run tests — all must pass
4. Commit: `release: vX.Y.Z`
5. Merge to `main`
6. Tag: `git tag vX.Y.Z`
7. Push: `git push origin main --tags`
8. CI builds `.exe` + signed MSIX and creates a GitHub Release

---

## Dependencies

| Package | Purpose |
| ------- | ------- |
| PySide6 | Qt 6 GUI framework |
| mss | GDI fallback screen capture |
| opencv-python | Video decode/encode, image processing |
| numpy | Array operations for frame manipulation |
| imageio-ffmpeg | Bundled ffmpeg binary |
| windows-capture | Windows Graphics Capture API bindings |

To add a dependency:

1. `pip install package-name`
2. Add to `requirements.txt` with a minimum version
3. If heavy and not needed at import time, use a deferred import

---

## Build & CI

### Local Build

```powershell
.\scripts\Build-App.ps1
```

Produces `dist\FollowCursor\FollowCursor.exe` — a single-folder PyInstaller distribution.

### MSIX Package

```powershell
# Unsigned (local testing)
.\scripts\Build-Msix.ps1 -Version "0.8.0" -SkipSign

# Signed with local PFX
.\scripts\Build-Msix.ps1 -Version "0.8.0" -LocalPfx ".\cert.pfx" -Publisher "CN=MyName"
```

### CI Pipeline

GitHub Actions runs on every push/PR to `main`:

1. Extracts version from `app/version.py`
2. Installs dependencies (Python 3.13, Windows runner)
3. Runs the pytest suite
4. Builds with PyInstaller
5. Uploads versioned artifact
6. On `v*` tags: builds MSIX, signs with Azure Trusted Signing, creates GitHub Release

---

## Questions?

Open an issue on GitHub or check the [Quickstart Guide](QUICKSTART.md) for usage help.
