# Architecture Guide

This document describes the internal architecture of FollowCursor: how the major subsystems work, how data flows through the app, and the key design decisions behind the implementation.

---

## High-Level Overview

```text
MainWindow
 |-- TitleBar (frameless, custom)
 |-- PreviewWidget (live / playback)
 |-- TimelineWidget (heatmap + keyframes + chapters)
 |-- EditorPanel (settings, controls)
 |-- GlobalHotkeys (Win32 RegisterHotKey)
 |-- ScreenRecorder (WGC / GDI + ffmpeg)
 |-- ZoomEngine (ease-out interpolation)
 +-- ActivityAnalyzer (auto-zoom)

ScreenRecorder
 |-- MouseTracker (60 Hz QTimer poll)
 |-- ClickTracker (Win32 WH_MOUSE_LL)
 +-- KeyboardTracker (Win32 WH_KEYBOARD_LL)

All trackers + ZoomEngine --> VideoExporter (ffmpeg H.264 pipe)
```

---

## App Lifecycle

### Two Modes: Record and Edit

The app operates in two modes, switchable via the sidebar:

1. **Record mode** — Live capture preview, source selection, countdown, recording controls
2. **Edit mode** — Video playback, timeline, zoom keyframe editing, visual customization, export

`MainWindow._set_view()` manages mode transitions, showing/hiding widgets and loading video when entering edit mode.

### Recording Flow

```text
User clicks Start
  --> CountdownOverlay shows 3-2-1
  --> _do_start_recording()
    --> ScreenRecorder.start_recording(shared_epoch)
    --> MouseTracker.start(shared_epoch_ms)
    --> KeyboardTracker.start(shared_epoch_ms)
    --> ClickTracker.start(shared_epoch_ms)
    --> RecordingBorder.show_on_monitor()
    --> App minimizes to tray

User presses Ctrl+Shift+R (stop)
  --> _stop_recording()
    --> All trackers stop
    --> recording_finished signal
    --> Restore app, switch to Edit mode
```

### Shared Epoch

All four data streams (video frames, mouse positions, keyboard events, click events) share a single `time.time()` epoch set at the start of recording. This ensures timestamps are perfectly aligned without post-hoc synchronization.

---

## Data Model

All data classes live in `app/models.py`.

### Core Types

| Class | Fields | Purpose |
| ----- | ------ | ------- |
| `MousePosition` | `x, y, timestamp` | Absolute screen coords at ~60 Hz |
| `KeyEvent` | `timestamp, x, y, vk_code` | Keystroke time + cursor position + virtual key code |
| `ClickEvent` | `x, y, timestamp` | Mouse click position + time |
| `ZoomKeyframe` | `id, timestamp, zoom, x, y, duration, reason, speed` | Zoom instruction with playback speed |
| `VideoSegment` | `id, start_ms, end_ms, speed` | Contiguous time range with speed multiplier |
| `VoiceoverSegment` | `id, timestamp, text, voice, audio_path, duration_ms, rate, volume` | TTS narration segment |
| `Chapter` | `timestamp_ms, name, auto_detected` | Scene boundary marker |
| `ClickEffectPreset` | `name, color, style, duration_ms, radius` | Click visual effect configuration |
| `KeystrokeOverlayConfig` | `enabled, position, style, filter_mode, ...` | Keystroke display settings |
| `TextAnnotation` | `id, start_ms, end_ms, x, y, text, ...` | Text overlay |
| `ArrowAnnotation` | `id, start_ms, end_ms, x1, y1, x2, y2, ...` | Directional arrow |
| `HighlightBox` | `id, start_ms, end_ms, x, y, width, height, ...` | Highlight rectangle |
| `AnnotationCollection` | Container for all annotation types | Aggregates text, arrows, highlights |
| `RecordingSession` | All of the above bundled | Serializable session data |

### ZoomKeyframe Anatomy

```text
ZoomKeyframe:
  id        -- UUID string (for tracking/deletion)
  timestamp -- when the zoom transition STARTS (ms)
  zoom      -- target zoom level (1.0 = no zoom, 2.0 = 2x)
  x, y      -- normalized pan center (0-1), (0.5, 0.5) = center
  duration  -- transition length (ms)
  reason    -- human-readable label
  speed     -- playback speed multiplier (0.5-10.0)
```

Zoom operations come in pairs: a **zoom-in** keyframe (`zoom > 1.0`) followed by a **zoom-out** keyframe (`zoom = 1.0`). The engine interpolates smoothly between them.

---

## Screen Capture

### Backend Selection

`ScreenRecorder` tries backends in order:

1. **Windows Graphics Capture (WGC)** — hardware-accelerated, lowest latency, requires Windows 10 1903+
2. **GDI fallback** — `mss` screenshot library, works everywhere but is CPU-based

### Recording Pipeline

```text
WGC / GDI (BGRA frames)
  --> ffmpeg stdin pipe
  --> H.264 intermediate MP4 (CRF 18, ultrafast)
```

- Frames piped as raw BGRA bytes to ffmpeg stdin
- H.264 intermediate reduces disk usage from ~50 GB/min to under 1 GB/min for 4K
- No temporary image files
- Hybrid sleep for sub-millisecond frame timing

### Window Capture

`PrintWindow` (Win32 API via ctypes) captures window content without bleed-through. Physical pixels (DPI-aware).

---

## Zoom Engine

`ZoomEngine` (`app/zoom_engine.py`) is a pure-Python keyframe interpolator.

### Easing Functions

- **Quintic ease-out** — zoom transitions. Fast start, asymptotic deceleration.
- **Quintic ease-in-out (smoothstep)** — pan point transitions. Zero velocity at both endpoints.

### Interpolation

`compute_at(time_ms)` finds the active keyframe, computes progress, applies easing, and linearly interpolates zoom level + pan position. Returns `(zoom, pan_x, pan_y)`.

### Pan Path Points

Intermediate `ZoomKeyframe` entries between zoom-in and zoom-out. Same zoom level, different positions. The engine interpolates between them using ease-in-out transitions.

### Undo / Redo

Snapshot-based stacks (max depth 50). Each snapshot captures zoom keyframes, click events, video segments, and voiceover segments. Drag operations create a single undo snapshot.

---

## Activity Analyzer

`ActivityAnalyzer` (`app/activity_analyzer.py`) auto-generates zoom keyframes.

### Signal Detection

**Typing zones** — mouse stationary + keys pressed. Score = KPS. Keystroke cursor position used when available.

**Click clusters** — 1+ clicks in 3-second window. Score = count x 1.2 (highest weighted). Even single clicks trigger zoom.

### Spatial-Aware Clustering

Peaks clustered by time AND spatial proximity. Same-type peaks close in position (< 15% normalized distance) merged into sustained zooms.

### Pan-While-Zoomed Chains

Consecutive clusters within 1500 ms grouped into chains (max 4). Camera stays zoomed and pans between clusters. Pan duration scales with distance (400-700 ms).

### Scene Chapters

`detect_chapters()` detects scene boundaries via idle gaps (>= 3s) and major position jumps. Chapter markers on timeline, embeddable as MP4 metadata.

---

## AI Service

`AIService` (`app/ai_service.py`) — optional AI features via Azure AI Foundry on background `QThread`.

### AI Smart Zoom

Activity summarized into per-second text, sent to LLM. Returns JSON array of zoom sections (max 50). Applied same as local auto-zoom.

### Voiceover (TTS)

Segment-based: users create `VoiceoverSegment` at timeline positions, synthesize via Azure TTS. Export merges audio with ffmpeg `adelay` + `amix`, muxed as AAC (192 kbps).

### Credential Security

API keys encrypted with **Windows DPAPI** via `credentials.py`. User-scoped encryption, decrypt on-demand, cleared from memory after use.

---

## Video Export

`VideoExporter` (`app/video_exporter.py`) renders final MP4 or GIF.

### Pipeline

```text
Phase 1: Probe source MP4 (FPS, frame count)
Phase 2: Build background + bezel layers
Phase 3: Merge voiceover audio (if any)
Phase 4: For each output timestamp:
  - Pick source frame (binary search)
  - Compose (zoom + annotations + cursor + clicks + keystrokes)
  - Enqueue to bounded queue (depth 16)
Phase 5: Writer thread drains queue --> ffmpeg --> MP4/GIF
```

### Overlay Z-Order (back to front)

1. Annotations (highlights, arrows, text)
2. Mouse cursor
3. Click effects (ripple/burst/highlight)
4. Keystroke badges

### Encoder Fallback

Two-phase: immediate check (100 ms) + mid-stream retry. Priority: NVENC --> QuickSync --> AMF --> libx264.

### GIF Export

Palette-based: `fps=15`, `palettegen` (diff mode), `paletteuse` (bayer dither). Single-pass.

---

## Compositor

Two implementations, identical output:

| Compositor | Technology | Used by |
| ---------- | ---------- | ------- |
| `compositor.py` | QPainter (Qt) | Live preview |
| `video_exporter.py` (inline) | NumPy + OpenCV | Export |

### Zoom by Frame Preset

- **No Frame**: zoom/pan on video only, background static
- **Device frame**: zoom/pan moves device as unit, background static

---

## Design System

### Design Tokens (`tokens.py`)

Centralized constants aligned with Windows 11 / Fluent 2:

| Category | Values |
| -------- | ------ |
| **Spacing** | 4px grid: XXS=4, XS=8, SM=12, MD=16, LG=24, XL=32, XXL=48 |
| **Radius** | RADIUS_SMALL=4px (controls), RADIUS_MEDIUM=8px (containers) |
| **Colors** | 5 bg layers, 3 border tiers, 4 fg levels, brand purple #8b5cf6, status colors |
| **Typography** | Segoe UI Variable, 5 sizes (caption 11 to header 20) |
| **Animation** | FAST=100ms, NORMAL=200ms, SLOW=300ms |
| **Shadows** | 2 levels (subtle, medium) |

### Visual Effects (`fluent_effects.py`)

- `apply_shadow(widget, level)` — QGraphicsDropShadowEffect
- `install_hover_animation(widget, ...)` — QPropertyAnimation via event filter
- `install_focus_ring(widget)` — brand-colored glow on keyboard focus

### Theme (`theme.py`)

Comprehensive QSS stylesheet using token references. All styling via QSS, not QPalette.

---

## Input Tracking

| Tracker | Method | Details |
| ------- | ------ | ------- |
| **Mouse** | QTimer at 60 Hz | Polls `QCursor.pos()` |
| **Keyboard** | Win32 WH_KEYBOARD_LL | Records timestamp + cursor position + VK code. Uses `WINFUNCTYPE` for 64-bit |
| **Click** | Win32 WH_MOUSE_LL | Left/right click detection with position |

All hooks run in dedicated threads with Win32 message loops. `CallNextHookEx` always called. Events appended to shared lists (CPython GIL thread-safe). Callbacks wrapped in try/except.

---

## UI Architecture

### Frameless Window

`Qt.WindowType.FramelessWindowHint` with custom `TitleBar`:

- Drag-to-move via `QWindow.startSystemMove()` (Aero Snap support)
- Double-click maximize/restore
- Minimize / maximize / close / export buttons

### Widget Communication

All inter-component communication via Qt signals and slots:

```text
EditorPanel.output_dimensions_changed --> MainWindow --> PreviewWidget.set_output_dim
TimelineWidget.segment_clicked --> MainWindow --> Context menu
PreviewWidget.zoom_at_requested --> MainWindow --> _add_keyframe
```

### Threading Model

| Thread | Purpose |
| ------ | ------- |
| Main (GUI) | Qt widgets, painting, events |
| Recording | WGC/GDI --> ffmpeg pipe |
| Keyboard hook | Win32 WH_KEYBOARD_LL |
| Click hook | Win32 WH_MOUSE_LL |
| Export | Frame render + ffmpeg pipe |
| Writer | Queue --> stdin (overlaps compositing with encoding) |
| Hotkey | Win32 RegisterHotKey + GetMessage |
| Thumbnail | Background source picker thumbnails |
| Project load | ZIP extraction + deserialization |

---

## Project Files

`.fcproj` files are ZIP archives:

```text
project.fcproj (ZIP)
  |-- project.json     -- session metadata
  |-- recording.mp4    -- H.264 intermediate video
  +-- voiceover_*.wav  -- synthesized audio files
```

### Incremental Save

`save_project(metadata_only=True)` rewrites only `project.json` in-place. Total I/O: O(JSON_size), typically a few KB regardless of video size.

---

## Build & Distribution

### PyInstaller

`Build-App.ps1` produces a single-folder distribution. 40+ unused PySide6 modules excluded.

### MSIX

`Build-Msix.ps1` packages into signed MSIX. Supports local PFX and Azure Trusted Signing.

### CI/CD

GitHub Actions on push/PR to `main` and `v*` tags. Python 3.13 on Windows. Runs pytest, builds with PyInstaller. On tag: MSIX + GitHub Release.

---

## Logging

Python `logging` module. Format: `%(name)s | %(levelname)s | %(message)s`. `RotatingFileHandler` writes ERROR+ to `%LOCALAPPDATA%/FollowCursor/error.log` (2 MB, 3 backups).

---

## Component Map

| File | Purpose |
| ---- | ------- |
| `main.py` | Entry point, QApplication setup |
| `app/version.py` | Semantic version (single source of truth) |
| `app/models.py` | All data classes with serialization |
| `app/main_window.py` | Central coordinator, state management |
| `app/screen_recorder.py` | WGC + ffmpeg pipe capture |
| `app/video_exporter.py` | H.264/GIF export with zoom/cursor |
| `app/compositor.py` | QPainter compositing for preview |
| `app/utils.py` | Helper functions for video/image processing |
| `app/zoom_engine.py` | Keyframe interpolation + undo/redo |
| `app/activity_analyzer.py` | Auto-zoom from activity |
| `app/ai_service.py` | AI zoom + TTS voiceover |
| `app/credentials.py` | DPAPI credential encryption |
| `app/mouse_tracker.py` | 60 Hz cursor polling |
| `app/keyboard_tracker.py` | Win32 keyboard hook |
| `app/click_tracker.py` | Win32 mouse click hook |
| `app/cursor_renderer.py` | Arrow cursor + click effects |
| `app/keystroke_renderer.py` | Keystroke badge overlay |
| `app/annotation_renderer.py` | Text, arrow, highlight rendering |
| `app/global_hotkeys.py` | Win32 RegisterHotKey |
| `app/window_utils.py` | Win32 window enumeration |
| `app/backgrounds.py` | 84 background presets |
| `app/frames.py` | 5 device frame presets |
| `app/project_file.py` | .fcproj save/load |
| `app/tokens.py` | Fluent 2 design tokens |
| `app/fluent_effects.py` | Shadows, animations, focus rings |
| `app/theme.py` | QSS dark theme stylesheet |
| `app/icon.py` | QPainter-generated app icon |
| `app/widgets/title_bar.py` | Custom frameless title bar |
| `app/widgets/source_picker.py` | Screen/Window selection dialog |
| `app/widgets/preview_widget.py` | Live/playback preview |
| `app/widgets/timeline_widget.py` | QPainter timeline with heatmap |
| `app/widgets/timeline_math.py` | Pixel-time conversion helpers |
| `app/widgets/editor_panel.py` | Collapsible editor sections |
| `app/widgets/countdown_overlay.py` | 3-2-1 countdown animation |
| `app/widgets/processing_overlay.py` | Pulsing banner overlay |
| `app/widgets/recording_border.py` | Red border during recording |
