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
 +-- KeyboardTracker (legacy no-op compatibility stub)

Mouse/click trackers + ZoomEngine --> VideoExporter (ffmpeg H.264 pipe)
```

---

## App Lifecycle

### Two Modes: Record and Edit

The app operates in two modes, switchable via the sidebar:

1. **Record mode** — Live capture preview, source selection, countdown, recording controls
2. **Edit mode** — Video playback, timeline, zoom keyframe editing, visual customization, export

`MainWindow._set_view()` manages mode transitions, showing/hiding widgets and loading video when entering edit mode.

The fixed post-recording `EditorPanel` separates work into Motion, Style, and Audio tabs. Multi-section tabs use exclusive disclosure so only one section body is open at a time. Related alternatives share compact action rows, and dynamic feedback is constrained to one line with the full message retained in its tooltip and accessible name.

### Startup Flow

`main.py` creates the `QApplication`, applies the app icon/palette, and shows a lightweight splash screen before constructing `MainWindow`. The theme-aware splash renders a miniature editing viewport with a camera path converging on the FollowCursor icon, giving the brief wait product-specific character without adding animation or delaying startup. `MainWindow._deferred_init()` then performs post-show work such as tray setup, encoder label refresh, and optional TTS voice preloading; when that first deferred pass completes, it emits `startup_ready` on the next event-loop turn so the splash can close without blocking startup on background voice loading.

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
    --> Existing project media is normalized and concatenated when adding a capture
    --> New event timestamps are offset and appended as a video segment
    --> Restore app, switch to Edit mode
```

### Shared Epoch

Video frames, mouse positions, clicks, and related activity signals share a single `time.time()` epoch set at the start of recording. This ensures timestamps are perfectly aligned without post-hoc synchronization.

When a capture is added to an existing project, its local timestamps are offset by the prior project duration. ffmpeg fits the new source into the original project canvas with aspect-ratio-preserving padding, and cursor coordinates are mapped through the same scale and padding. The bundle keeps a single `recording.mp4`, so older project files and the single-path preview/export pipeline remain compatible.

---

## Data Model

All data classes live in `app/models.py`.

### Core Types

| Class | Fields | Purpose |
| ----- | ------ | ------- |
| `MousePosition` | `x, y, timestamp` | Absolute screen coords at ~60 Hz |
| `ClickEvent` | `x, y, timestamp` | Mouse click position + time |
| `ZoomKeyframe` | `id, timestamp, zoom, x, y, duration, reason, speed` | Zoom instruction with playback speed |
| `VideoSegment` | `id, start_ms, end_ms, speed` | Contiguous time range with speed multiplier |
| `VoiceoverSegment` | `id, timestamp, text, voice, audio_path, duration_ms, rate, volume, source, script_markdown, script_path` | Manual voiceover or generated voiceover segment |
| `Chapter` | `timestamp_ms, name, auto_detected` | Scene boundary marker |
| `ClickEffectPreset` | `name, color, style, duration_ms, radius` | Click visual effect configuration |
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

**Low-motion activity zones** — mouse stationary during a burst of interaction. Score = activity density in the window.

**Click clusters** — 1+ clicks in 3-second window. Score = count x 1.2 (highest weighted). Even single clicks trigger zoom.

### Spatial-Aware Clustering

Peaks clustered by time AND spatial proximity. Same-type peaks close in position (< 15% normalized distance) merged into sustained zooms.

### Pan-While-Zoomed Chains

Consecutive clusters within 1500 ms grouped into chains (max 4). Camera stays zoomed and pans between clusters. Pan duration scales with distance (400-700 ms).

### AI Chapters

Chapter generation now runs through `AIService.generate_chapters()`. It reuses the same shared recording knowledge as narration — frame samples, activity summary, click beats, zoom edits, and provider-safe batch notes — so chapter markers stay aligned with the presentation beats already visible to narration. Generated chapter markers can replace prior generated markers while preserving any manual chapters on the timeline, and the merged set is embeddable as MP4 metadata.

---

## AI Service

`AIService` (`app/ai_service.py`) — optional AI features via Azure AI Foundry on background `QThread`.

### AI Smart Zoom

Activity summarized into per-second text, sent to LLM. Returns JSON array of zoom sections (max 50). Applied same as local auto-zoom.

### Automated narration

The narration path builds a `SharedRecordingKnowledge` artifact from steady frame samples plus mouse activity, clicks, and authoritative zoom keyframes. When the full frame pack would exceed the provider image cap, FollowCursor sends multimodal batches to **GPT-5.4**, saves the batch notes, and reuses those notes for both narration and chapter generation. Narration synthesizes that shared evidence into five timed voiceover drafts with **Context**, **Background**, **Prompt / Action**, **Walkthrough**, and **Result**. If the draft is too short or too long for the recording, a text-only pacing polish rewrites the same five sections against their timing windows before TTS. The final prompt steers the model toward a peer presentation or pitch instead of cursor-by-cursor recap prose, and the polish pass rewrites literal click/zoom/camera phrasing into action- or outcome-focused language when needed. FollowCursor saves the combined markdown beside the recording as `<video_name>_voiceover.md`, creates generated `VoiceoverSegment` entries, and then hands those segments to the same TTS path used by **Add voiceover** so each segment becomes a normal timeline WAV clip. Ripple clip deletes trim and retime overlapping generated narration segments, rewrite the markdown sidecar, and re-synthesize only the affected generated clips so narration stays aligned with the edited cut. TTS can retry each segment with a small speech-rate nudge (within ±12%) so the combined narration stays within about 1.5 seconds or 1.5% of the video duration, whichever is larger, without obvious silence padding.

### Voiceover (TTS)

Segment-based: users can create manual `VoiceoverSegment` entries at timeline positions, and generated narration is stored as timed generated `VoiceoverSegment` entries. Export merges all synthesized audio with ffmpeg `adelay` + `amix`, muxed as AAC (192 kbps).

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
  - Compose (zoom + cursor + clicks)
  - Enqueue to bounded queue (depth 16)
Phase 5: Writer thread drains queue --> ffmpeg --> MP4/GIF
```

### Overlay Z-Order (back to front)

1. Mouse cursor
2. Click effects (ripple/burst/highlight)

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
| **Click** | Win32 WH_MOUSE_LL | Left/right click detection with position |
| **Keyboard (legacy)** | Compatibility stub | No hook is installed. Retained for ABI tests and older controller paths while removed keystroke data is ignored. |

Only mouse and click activity feed the current product UI and automation. The legacy keyboard tracker remains import-compatible but does not install a hook or emit keystrokes. Legacy annotation payloads are also ignored during project load, so export, narration, and chapter generation only consume mouse, click, frame, and zoom context.

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
  |-- project.json     -- session metadata + generated narration markdown
  |-- recording.mp4    -- H.264 intermediate video
  +-- voiceover_*.wav  -- synthesized audio files
```

When you load a project, `MainWindow` recombines generated voiceover segment markdown into a fresh `<video_name>_voiceover.md` sidecar beside the extracted recording.

### Incremental Save

`save_project(metadata_only=True)` rewrites only `project.json` in-place. Total I/O: O(JSON_size), typically a few KB regardless of video size.

Adding a capture marks project media as changed. The next save performs a full bundle write so the concatenated `recording.mp4` replaces the prior ZIP entry; subsequent saves can use the metadata-only path again.

---

## Build & Distribution

### PyInstaller

`Build-App.ps1` produces a single-folder distribution. 40+ unused PySide6 modules excluded.

### MSIX

`Build-Msix.ps1` packages the PyInstaller output. It supports a local PFX or Azure Trusted Signing.

Tag CI retains an unsigned MSIX as a short-lived artifact. `Publish-SignedMsix.ps1` downloads and signs that artifact with the local Azure user. It verifies the signature, timestamp, and manifest publisher. Then it uploads the MSIX to the GitHub Release.

### CI/CD

GitHub Actions runs on push and pull requests to `main`. It also runs on `v*` tags with Python 3.13 on Windows. It runs pytest and builds with PyInstaller. On tags, it publishes the ZIP and creates the GitHub Release. It retains the unsigned MSIX for seven days.

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
| `app/ai_service.py` | AI zoom, multimodal narration, and TTS voiceover |
| `app/credentials.py` | DPAPI credential encryption |
| `app/mouse_tracker.py` | 60 Hz cursor polling |
| `app/keyboard_tracker.py` | Legacy no-op compatibility stub for removed keystrokes |
| `app/click_tracker.py` | Win32 mouse click hook |
| `app/cursor_renderer.py` | Arrow cursor + click effects |
| `app/global_hotkeys.py` | Win32 RegisterHotKey |
| `app/window_utils.py` | Win32 window enumeration |
| `app/backgrounds.py` | 84 background presets |
| `app/frames.py` | 5 device frame presets |
| `app/project_file.py` | .fcproj save/load |
| `app/tokens.py` | Fluent 2 design tokens |
| `app/fluent_effects.py` | Shadows, animations, focus rings |
| `app/theme.py` | QSS dark theme stylesheet |
| `app/icon.py` | QPainter-generated app icon |
| `app/splash_screen.py` | Runtime startup splash rendering and dismissal helpers |
| `app/widgets/title_bar.py` | Custom frameless title bar |
| `app/widgets/source_picker.py` | Screen/Window selection dialog |
| `app/widgets/preview_widget.py` | Live/playback preview |
| `app/widgets/timeline_widget.py` | QPainter timeline with heatmap |
| `app/widgets/timeline_math.py` | Pixel-time conversion helpers |
| `app/widgets/editor_panel.py` | Task-tabbed Motion, Style, and Audio inspector controls |
| `app/widgets/countdown_overlay.py` | 3-2-1 countdown animation |
| `app/widgets/processing_overlay.py` | Pulsing banner overlay |
| `app/widgets/recording_border.py` | Red border during recording |
