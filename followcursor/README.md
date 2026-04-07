# FollowCursor

A Windows screen recorder with cinematic cursor-following zoom — built with **Python** and **PySide6 (Qt 6)**.

Record your screen or any individual window, then export a polished MP4 video where the camera smoothly follows and zooms into your cursor movements. Perfect for tutorials, demos, and product walkthroughs.

![FollowCursor screenshot](../screenshot.png)

> **New here?** Jump to the [Quickstart Guide](../docs/QUICKSTART.md) to get recording in under 5 minutes.
>
> **📖 Full documentation:** [sabbour.me/followcursor](https://sabbour.me/followcursor)

## Documentation

| Document | Description |
| -------- | ----------- |
| [**Documentation Site**](https://sabbour.me/followcursor) | Full docs site with search and navigation |
| [User Guide](../docs/USER_GUIDE.md) | Complete feature reference — every feature explained |
| [Quickstart Guide](../docs/QUICKSTART.md) | Install, record, edit, export — step by step |
| [Architecture Guide](../docs/ARCHITECTURE.md) | How the codebase works: data flow, zoom engine, capture pipeline |
| [Contributing Guide](../docs/CONTRIBUTING.md) | Dev setup, coding conventions, release process |

## Features

- **Screen & Window Recording** — Capture any monitor (hardware-accelerated via Windows Graphics Capture) or individual windows
- **Smart Auto-Zoom** — Automatically detects typing bursts and click clusters to generate zoom keyframes with configurable sensitivity (Low / Medium / High). Spatial-aware clustering merges nearby same-area events into sustained zooms, and consecutive clusters are chained together (up to 4 per chain) — the camera stays zoomed in and pans smoothly between them instead of zooming out and back in
- **AI Smart Zoom** — Use Azure AI Foundry chat models to analyze your recording and generate intelligent zoom-and-pan keyframes. The AI acts like a professional cameraman — identifying significant activity, creating smooth sustained zooms with panning when action moves across the screen, and maintaining calm, deliberate pacing. Bring your own Azure OpenAI API key
- **AI Voiceover (TTS)** — Add text-to-speech voiceover segments at specific timeline positions via right-click or the editor panel. Enter text, pick from 6 voices (alloy, echo, fable, onyx, nova, shimmer), preview synthesized speech, or add it directly. Multiple segments are merged and muxed into the exported MP4. Voiceover audio is saved in .fcproj project files
- **Manual Zoom Keyframes** — Right-click the timeline or preview to add zoom points; drag segments to reposition them
- **Pan Path Points** — Add intermediate pan waypoints within a zoomed segment to create a smooth panning path through the zoomed view. Numbered markers show the order; drag, reorder, or delete them from the context menu
- **Zoom Depth Control** — Right-click a zoom segment to set depth (Subtle 1.25×, Medium 1.5×, Close 2×, Detail 2.5×)
- **Centroid Editing** — Reposition the pan center of any zoom keyframe by clicking "Set centroid" on a zoom segment, then clicking the target point on the preview
- **Live Zoom Shortcuts** — `Ctrl+Shift+=` / `Ctrl+Shift+-` to zoom in/out during recording (global hotkeys)
- **Mouse & Click Tracking** — Records cursor position at 60 Hz, keyboard events, and click events with visual markers
- **Click Selection & Deletion** — Select individual click events on the timeline and delete unwanted ones
- **Timeline Editor** — Visual timeline with mouse-speed heatmap, gradient-styled zoom segments, draggable edges, and click-to-seek
- **Trimming** — Drag trim handles on the timeline edges to cut unwanted content from the start or end of your recording; export respects the trimmed range
- **Undo & Redo** — Full undo/redo for all zoom keyframe and click event changes (Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y), up to 50 levels deep
- **Cinematic Export** — H.264 MP4 via ffmpeg with ease-out easing, cursor rendering, click ripple effects, and device frame overlays. Supports GPU-accelerated encoding (NVENC, QuickSync, AMF) with automatic detection and fallback to software x264. Status bar shows active encoder name during export
- **Output Dimensions** — Choose from Auto, 16:9, 3:2, 4:3, 1:1, or 9:16 aspect ratios for the exported video. Preview shows crop boundaries with a semi-transparent overlay
- **Background Presets** — 84 backgrounds (39 solids + 37 gradients + 8 patterns) with category picker
- **Device Frames** — 5 frame styles: Wide Bezel, Slim Bezel, Thin Border, Shadow Only, No Frame
- **Project Files** — Save/load `.fcproj` bundles (ZIP with metadata + raw video + voiceover audio) to resume editing later. Ctrl+S re-saves to the current file with incremental metadata-only updates (video is not re-written). Title bar shows project name and unsaved-changes indicator (●). Export filename defaults to the project name
- **Close Confirmation** — Prompts to save unsaved changes before closing the app
- **Open in Clipchamp** — One-click handoff to Clipchamp for further editing
- **Debug Overlay** — Per-time zoom marker overlay on the preview for fine-tuning keyframes (toggle via ⚙ settings menu)
- **3-Second Countdown** — Visual countdown before recording starts
- **Frameless Dark UI** — Custom title bar, dark theme with purple accents

## Architecture

| Layer | Technology | Purpose |
| ----- | ---------- | ------- |
| UI Framework | PySide6 (Qt 6) | Widgets, layout, painting, signals/slots |
| Screen Capture | Windows Graphics Capture (WGC) | Hardware-accelerated monitor/window capture |
| Window Capture | Win32 PrintWindow (ctypes) | Per-window capture without bleed-through |
| Recording Pipe | ffmpeg via imageio-ffmpeg | H.264 intermediate codec (CRF 18, ultrafast) piped via stdin; reduces temp file size from ~50 GB/min to under 1 GB/min for 4K recordings |
| Video Export | ffmpeg (libx264 / HW accel) | H.264 MP4 encoding (CRF 18 equivalent) with zoom/cursor baked in; auto-detects NVENC, QuickSync, AMF |
| Image Processing | OpenCV + NumPy | Frame manipulation, thumbnails, cursor rendering |
| Input Tracking | Win32 Hooks (ctypes) | Low-level mouse, keyboard, and click tracking |
| Zoom Engine | Pure Python | Ease-out-eased keyframe interpolation |
| AI Features | azure-ai-inference | Optional AI zoom analysis (with panning), TTS voiceover via Azure AI Foundry |

## Getting Started

### Prerequisites

- **Windows 10/11**
- **Python 3.10+** — [Download](https://www.python.org/downloads/) (check "Add to PATH" during install)  
  > **ARM64 Windows:** Install the **x64** edition — ARM64 native Python is not supported.

### Quick Start

```powershell
.\scripts\Start-Dev.ps1
```

Creates a virtual environment, installs dependencies, and launches the app.

### Manual Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Building

Build a standalone `.exe` with PyInstaller:

```powershell
.\scripts\Build-App.ps1
```

Output: `dist\FollowCursor\FollowCursor.exe`

The build script automatically creates a virtual environment and installs all dependencies if needed.

### VS Code Tasks

All build steps are available as VS Code tasks (`Ctrl+Shift+P` → **Tasks: Run Task**):

| Task | What it does |
| ---- | ------------ |
| **Run** | Launches the app from source (`main.py`) |
| **Start Dev** | Creates venv, installs deps, then launches the app |
| **Build** (`Ctrl+Shift+B`) | Runs `Build-App.ps1` — produces `dist\FollowCursor\FollowCursor.exe` |
| **Build MSIX (Unsigned)** | Builds the app, then packages an unsigned `.msix` for local testing |
| **Build MSIX (Signed with PFX)** | Builds the app, then packages and signs the `.msix` with a local certificate |
| **Install Dependencies** | Runs `pip install -r requirements.txt` into the venv |
| **Run Tests** | Runs the pytest suite — **always run before merging or releasing** |
| **Create Dev Signing Certificate** | Creates a self-signed certificate for local MSIX sideloading (no admin required) |

The MSIX tasks depend on **Build** and will run it automatically first. When prompted, enter the version string (e.g. `0.6.0`) and, for signed builds, the certificate subject and `.pfx` path.

### MSIX Package

To produce a single-file installer (`.msix`), first run `Build-App.ps1` to create the
PyInstaller output, then run `Build-Msix.ps1` to package and optionally sign it:

```powershell
# Unsigned (local testing / sideloading)
.\scripts\Build-Msix.ps1 -Version "0.5.0" -SkipSign

# Sign with a local PFX certificate
.\scripts\Build-Msix.ps1 -Version "0.5.0" -LocalPfx ".\cert.pfx" -Publisher "CN=MyName"

# Sign with Azure Trusted Signing (local)
.\scripts\Build-Msix.ps1 -Version "0.5.0" -Publisher "CN=..." `
  -AzureEndpoint "https://eus.codesigning.azure.net/" `
  -AzureCodeSigningAccountName "myacct" `
  -AzureCertificateProfileName "myprofile"

# Sign with Azure Trusted Signing using a custom DLib path
.\scripts\Build-Msix.ps1 -Version "0.5.0" -Publisher "CN=..." `
  -AzureEndpoint "https://eus.codesigning.azure.net/" `
  -AzureCodeSigningAccountName "myacct" `
  -AzureCertificateProfileName "myprofile" `
  -DlibPath "C:\signing\Azure.CodeSigning.Dlib.dll"
```

Requires the Windows SDK (`MakeAppx.exe`, `SignTool.exe`).

#### Local Sideloading with a Self-Signed Certificate

Unsigned MSIX packages cannot be installed directly — Windows requires a trusted
signature. For local testing, create a self-signed certificate and trust it on your
machine. You can run the **Create Dev Signing Certificate** VS Code task, or run
these commands manually in PowerShell:

```powershell
# 1. Create a self-signed code-signing certificate
$cert = New-SelfSignedCertificate -Type Custom -Subject "CN=FollowCursor-Dev" `
    -KeyUsage DigitalSignature -FriendlyName "FollowCursor Dev" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3")

# 2. Trust the certificate (allows MSIX install without Store)
Export-Certificate -Cert $cert -FilePath "$env:TEMP\FollowCursor-Dev.cer"
Import-Certificate -FilePath "$env:TEMP\FollowCursor-Dev.cer" `
    -CertStoreLocation "Cert:\CurrentUser\TrustedPeople"

# 3. Export a PFX for signing builds
Export-PfxCertificate -Cert $cert -FilePath "$env:TEMP\FollowCursor-Dev.pfx" `
    -Password (ConvertTo-SecureString -String "dev" -Force -AsPlainText)
```

Then build and sign the MSIX with that certificate:

```powershell
.\scripts\Build-Msix.ps1 -Version "0.7.0" `
    -Publisher "CN=FollowCursor-Dev" `
    -LocalPfx "$env:TEMP\FollowCursor-Dev.pfx" `
    -PfxPassword "dev"
```

The resulting `.msix` can be double-clicked to install on the same machine.

## CI/CD

A GitHub Actions workflow (`.github/workflows/build.yml`) runs on every push/PR to `main`:

1. Sets up Python 3.13 on a Windows runner
2. Extracts the app version from `app/version.py`
3. Installs dependencies
4. Runs the pytest test suite
5. Builds with PyInstaller
6. Uploads the versioned build artifact (retained 30 days)
7. On tag pushes (`v*`): builds an unsigned MSIX, signs it with `azure/artifact-signing-action`, and creates a GitHub Release

You can also trigger a build manually from the Actions tab.

### Releasing a new version

1. Update `__version__` in `followcursor/app/version.py`
2. Add a new section to `CHANGELOG.md` with today's date
3. Run the **Run Tests** VS Code task — all tests must pass
4. Commit and push to `main`
5. Tag the commit: `git tag v0.2.0 && git push --tags`
6. The CI workflow automatically builds the `.exe` + signed `.msix` and creates a GitHub Release

To build locally before tagging, use the **Build** task (`Ctrl+Shift+B`) or the **Build MSIX** tasks from the VS Code task list.

## Security

### Encrypted Credentials

FollowCursor protects your Azure AI Foundry API keys using Windows DPAPI (Data Protection API):

- **At rest:** API keys stored in the Windows Registry are encrypted with your user account credentials via DPAPI. Credentials are encrypted using DPAPI when available. On systems where DPAPI is unavailable, credentials are stored with reduced protection.
- **In memory:** API keys are decrypted on-demand when connecting to AI services and are not persisted beyond the active session.

### Temporary Files

Recording and export operations create temporary files in your system's temp directory (`%TEMP%`). FollowCursor implements safe cleanup:

- **Recording temp files** — intermediate video frames are deleted automatically when starting a new recording or exiting the app
- **Unique filenames** — voiceover merge operations use randomized temp filenames to prevent collisions in concurrent operations
- **Project extraction** — extracted project directories are tracked and removed on exit, even if an error occurs
- **No leaks** — all temp directories are cleaned up during normal shutdown; unclean exits are handled via temporary cleanup on app launch



| Shortcut | Action |
| -------- | ------ |
| `Space` | Play / pause playback (edit view) |
| `Z` | Insert zoom keyframe at playhead (edit view) |
| `Ctrl+Shift+=` | Zoom in at cursor position |
| `Ctrl+Shift+-` | Zoom out to 1.0× |
| `Ctrl+S` | Save project (re-saves to current file) |
| `Ctrl+Z` | Undo last zoom/click change |
| `Ctrl+Shift+Z` / `Ctrl+Y` | Redo last undone change |
| Right-click zoom segment | Edit depth / centroid / delete |
| Right-click preview | Add zoom at click position |\n| Right-click timeline (empty) | Add zoom or voiceover at position |
| Drag zoom segment edge | Reposition zoom in timeline |
| Left-click event dot | Select click event |
| `Delete` | Remove selected click event |
| Drag timeline edge handles | Set trim start/end point |

## Project Structure

```text
followcursor/
├── main.py                          # Entry point, QApplication setup
├── requirements.txt                 # Python dependencies
├── generate_msix_assets.py           # Generate MSIX tile PNGs from app icon
├── followcursor.ico                 # App icon
├── pytest.ini                       # Pytest configuration
├── msix/                            # MSIX packaging files
│   ├── AppxManifest.xml              # Package manifest template
│   └── Assets/                       # Generated tile PNGs (gitignored)
├── scripts/                         # Build & infra PowerShell scripts
│   ├── Build-App.ps1                # PyInstaller build script
│   ├── Start-Dev.ps1                # Dev setup & launch script
│   ├── Build-Msix.ps1               # MSIX packaging + signing (local PFX or Azure)
│   └── Setup-AzureSigning.ps1        # Provision Azure Trusted Signing resources
├── tests/                           # Unit test suite (pytest)
│   ├── conftest.py                  # Shared fixtures
│   ├── test_models.py               # Dataclass serialization roundtrips
│   ├── test_zoom_engine.py          # Interpolation, undo/redo
│   ├── test_activity_analyzer.py    # Cluster detection, chains, overlap
│   ├── test_utils.py                # fmt_time, encoder args
│   ├── test_frames_backgrounds.py   # Preset data & serialization
│   ├── test_project_file.py         # .fcproj save/load roundtrips
│   └── test_ai_service.py           # AI settings, activity summary, zoom response parsing
├── app/
│   ├── version.py                   # Semantic version (__version__)
│   ├── models.py                    # Data classes (MousePosition, ZoomKeyframe, ClickEvent, …)
│   ├── utils.py                     # Shared helpers (ffmpeg path, encoder detection, subprocess, time formatting)
│   ├── zoom_engine.py               # Ease-out keyframe interpolation
│   ├── mouse_tracker.py             # QTimer-based cursor polling (60 Hz)
│   ├── keyboard_tracker.py          # Win32 keyboard hook
│   ├── click_tracker.py             # Win32 mouse click hook
│   ├── activity_analyzer.py         # Auto-zoom from mouse/keyboard/click activity
│   ├── ai_service.py                # AI zoom+pan analysis, TTS voiceover (Azure AI Foundry)
│   ├── screen_recorder.py           # WGC + ffmpeg pipe in background thread
│   ├── window_utils.py              # Win32 window enumeration & PrintWindow
│   ├── video_exporter.py            # H.264 MP4 export with zoom & cursor
│   ├── compositor.py                # QPainter compositing (frame + background)
│   ├── cursor_renderer.py           # Arrow cursor + click effect rendering (ripple/burst/highlight)
│   ├── annotation_renderer.py       # Text, arrow, and highlight annotation rendering
│   ├── keystroke_renderer.py        # Keystroke badge overlay for preview and export
│   ├── global_hotkeys.py            # Win32 RegisterHotKey via QThread
│   ├── backgrounds.py               # 84 background presets (solids, gradients, patterns)
│   ├── frames.py                    # 5 device frame presets
│   ├── project_file.py              # .fcproj save/load (ZIP bundle with voiceover audio)
│   ├── icon.py                      # QPainter-generated app icon
│   ├── theme.py                     # QSS dark theme stylesheet
│   ├── main_window.py               # Main window — assembles all widgets
│   └── widgets/
│       ├── title_bar.py             # Custom frameless title bar
│       ├── source_picker.py         # Screen/Window selection dialog (tabbed)
│       ├── preview_widget.py        # Live / playback preview with zoom/pan
│       ├── timeline_widget.py       # QPainter timeline with heatmap, keyframes, & chapters
│       ├── timeline_math.py        # Pixel↔time conversion helpers for timeline
│       ├── editor_panel.py          # Collapsible sections: zoom, voiceover, background, frame, click effects, keystroke overlay, annotations, chapters, output
│       ├── countdown_overlay.py     # 3-2-1 countdown animation
│       ├── processing_overlay.py    # Pulsing banner while finishing recording
│       └── recording_border.py      # Red border during recording
```
