# FollowCursor — Architecture Guide

This document describes the internal architecture of FollowCursor: how the major subsystems work, how data flows through the app, and the key design decisions behind the implementation.

---

## High-Level Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                        MainWindow                               │
│  Assembles all widgets and coordinates state transitions        │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  │
│  │ TitleBar  │  │ PreviewWidget│  │ Timeline │  │ EditorPanel│  │
│  │(frameless)│  │ (live/play)  │  │ (heatmap)│  │ (settings) │  │
│  └──────────┘  └──────────────┘  └──────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────┘
        │                │                │              │
        ▼                ▼                ▼              ▼
  ┌──────────┐   ┌─────────────┐  ┌───────────┐  ┌───────────┐
  │GlobalHotkeys│ │ScreenRecorder│ │ZoomEngine │  │ActivityAn.│
  │(Win32 hook)│ │(WGC/ffmpeg)  │ │(smoothstep)│ │(auto-zoom) │
  └──────────┘   └─────────────┘  └───────────┘  └───────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
       ┌────────────┐   ┌──────────────┐
       │MouseTracker │   │ClickTracker  │
       │(60Hz poll)  │   │(Win32 hook)  │
       └────────────┘   └──────────────┘
              │                 │
              ▼                 ▼
       ┌─────────────────────────────┐
       │     VideoExporter           │
       │  (ffmpeg H.264 pipe)        │
       └─────────────────────────────┘
```

---

## App Lifecycle

### Two modes: Record → Edit

The app operates in two modes, switchable via the **sidebar**:

1. **Record mode** — Live capture preview, source selection, countdown, recording controls
2. **Edit mode** — Video playback, timeline, zoom keyframe editing, background/frame selection, export

`MainWindow._set_view()` manages the mode transition, showing/hiding widgets and loading video for playback when entering edit mode.

### Recording flow

```text
User clicks Start → 3-2-1 Countdown → _do_start_recording()
  ├─ ScreenRecorder.start_recording(shared_epoch)
  ├─ MouseTracker.start(shared_epoch_ms)
  ├─ KeyboardTracker.start(shared_epoch_ms)
  ├─ ClickTracker.start(shared_epoch_ms)
  ├─ RecordingBorderOverlay.show_on_monitor()
  └─ App minimizes to system tray

User presses Ctrl+Shift+R → _stop_recording()
  ├─ ScreenRecorder.stop_recording()  ← async, emits recording_finished
  ├─ MouseTracker.stop()
  ├─ KeyboardTracker.stop()
  ├─ ClickTracker.stop()
  ├─ RecordingBorderOverlay.hide_border()
  └─ App restores, switches to Edit mode
```

### Shared epoch

All four data streams (video frames, mouse positions, keyboard events, click events) share a single `time.time()` epoch set at the start of recording. This ensures timestamps are perfectly aligned without post-hoc synchronization.

---

## Data Model

All data classes live in `app/models.py`.

### Core types

| Class | Fields | Purpose |
| ----- | ------ | ------- |
| `MousePosition` | `x, y, timestamp` | Absolute screen coords at ~60 Hz |
| `KeyEvent` | `timestamp` | Keystroke time (no key identity — privacy) |
| `ClickEvent` | `x, y, timestamp` | Mouse click position + time |
| `ZoomKeyframe` | `id, timestamp, zoom, x, y, duration, reason` | Zoom instruction |
| `RecordingSession` | All of the above bundled + trim range | Serializable session data |

### ZoomKeyframe anatomy

```text
ZoomKeyframe:
  id        — UUID string (for tracking/deletion)
  timestamp — when the zoom transition STARTS (ms)
  zoom      — target zoom level (1.0 = no zoom, 2.0 = 2×)
  x, y      — normalized pan center (0-1), (0.5, 0.5) = center
  duration  — how long the transition takes (ms), eased via ease-out curve
  reason    — human-readable label ("Typing activity detected")
```

Zoom operations always come in pairs: a **zoom-in** keyframe (`zoom > 1.0`) followed by a **zoom-out** keyframe (`zoom = 1.0`). The engine interpolates smoothly between them.

---

## Screen Capture

### Backend selection

`ScreenRecorder` tries backends in order:

1. **Windows Graphics Capture (WGC)** — hardware-accelerated, lowest latency, requires Windows 10 1903+
2. **GDI fallback** — `mss` screenshot library, works everywhere but is CPU-based

The active backend is shown in the status bar (`⚡ WGC` or `🖥 GDI`).

### Recording pipeline

```text
WGC/GDI frames (BGRA) → ffmpeg stdin pipe → lossless AVI (huffyuv codec)
```

- Frames are piped as raw BGRA bytes directly to ffmpeg's stdin
- Intermediate format is **huffyuv** (lossless) inside AVI — fast to write, preserves quality
- No temporary image files are created
- A hybrid sleep function (`_precise_sleep`) uses coarse sleep + spin-wait for sub-millisecond frame timing accuracy

### Window capture

For individual windows, `PrintWindow` (Win32 API via ctypes) captures the window content without bleed-through from overlapping windows. The captured buffer is in physical pixels (DPI-aware).

---

## Zoom Engine

`ZoomEngine` (`app/zoom_engine.py`) is a pure-Python keyframe interpolator:

### Ease-out easing

```python
def ease_out(t: float) -> float:
    """Cubic ease-out — fast start, asymptotic deceleration to zero."""
    return 1.0 - (1.0 - t) ** 3
```

This produces $1 - (1-t)^3$ — a cubic curve that starts fast and decelerates smoothly to zero velocity at $t=1$. The result is a natural "glide to a stop" for all zoom and pan transitions. The old `smooth_step` name is kept as an alias for backward compatibility.

### Interpolation

`compute_at(time_ms)` finds the active keyframe, computes progress through its transition, applies the ease-out curve, and interpolates zoom level + pan position linearly.

```text
time_ms → find active keyframe → elapsed/duration → ease_out(t) → lerp(prev, target)
```

Returns `(zoom, pan_x, pan_y)` — consumed by both the live preview and the video exporter.

### Undo / Redo

`ZoomEngine` maintains snapshot-based undo/redo stacks (max depth 50). Before any keyframe mutation, the caller invokes `push_undo()` which stores a `copy.deepcopy()` of the current keyframe list. `undo()` swaps the current state with the top of the undo stack (pushing the current state onto redo), and `redo()` does the reverse.

Drag operations use a debounce flag (`_drag_undo_pushed`) so that a continuous drag only creates a single undo snapshot. The flag resets when the mouse is released (`drag_finished` signal).

---

## Activity Analyzer

`ActivityAnalyzer` (`app/activity_analyzer.py`) auto-generates zoom keyframes by analyzing recorded input data. It detects three signal types:

### 1. Mouse settlements

Detects when the cursor moves fast then **stops** — the destination is where the user is focusing.

- Computes per-window velocity, detects deceleration ratio ≥ 3×
- Score = deceleration magnitude × `WEIGHT_MOUSE (0.5)`

### 2. Typing zones

Detects when the mouse is nearly stationary while keys are being pressed — indicates text editing.

- Requires mouse speed < 3 px/ms and keystrokes-per-second ≥ 1.0
- Score = KPS × `WEIGHT_TYPING (1.0)` — highest-weighted signal

### 3. Click clusters

Detects ≥ 2 mouse clicks within a 3-second sliding window — indicates interactive work.

- Zoom targets the centroid of the click positions
- Score = click count × `WEIGHT_CLICK (0.8)`

### Keyboard event filtering

The keyboard tracker (`keyboard_tracker.py`) uses a Win32 low-level hook (`WH_KEYBOARD_LL`). To prevent modifier keys and app hotkey combos from inflating typing activity signals, the hook checks the virtual key code from `KBDLLHOOKSTRUCT` and skips:

- Modifier keys: Ctrl, Shift, Alt, Win (both generic and left/right variants)
- Lock keys: CapsLock, NumLock, ScrollLock
- App hotkey keys: R (`0x52`), `=` (`0xBB`), `-` (`0xBD`)

These key-down events are still passed along via `CallNextHookEx` so other hooks and the hotkey system work normally — they are simply not recorded as `KeyEvent` timestamps.

### Spatial-aware clustering

After peak detection, peaks are clustered not just by time proximity but also by **spatial proximity**. Same-type peaks (click or typing) that are close in screen position (< 15% normalised distance) are merged into the same cluster even if their time gap exceeds the base `min_gap_ms` — up to 8 s for clicks and 6 s for typing. This prevents repeated zoom-out / zoom-in cycles when the user clicks or types in the same area with small pauses.

Merged clusters use the full time range (first peak → last peak) for zoom-in / zoom-out timing, so the camera stays zoomed in for the entire activity span rather than just a single peak moment.

### Maximum cluster duration

After spatial clustering, any cluster whose time span exceeds `MAX_CLUSTER_DURATION_MS` (8000 ms) is split into sub-clusters by walking through its peaks and starting a new sub-cluster whenever the next peak would push the span past the limit. This prevents a single zoom block from spanning the entire video when activity (e.g. form-filling) is spread continuously across many seconds.

### Pan-while-zoomed chains

After spatial clustering, consecutive clusters whose gaps are within `PAN_MERGE_GAP_MS` (1500 ms) are grouped into **chains**. Chains are capped at `MAX_CHAIN_LENGTH = 4` clusters — if more consecutive clusters exist, a new chain starts. The gap is measured from the actual activity **end** of one cluster to the **start** of the next (the hold/dwell period is excluded from the gap calculation so it doesn't cause unintended chaining). Within a chain:

- The camera **zooms in** at the first cluster
- For each subsequent cluster, a **pan keyframe** slides the viewport to the new target while staying zoomed — no zoom-out / zoom-in cycle
- Pan transition duration scales with screen distance (`PAN_TRANSITION_MS = 400` ms minimum, `PAN_TRANSITION_MAX_MS = 700` ms maximum)
- The camera **zooms out** only after the last cluster in the chain

Pan keyframes receive a reason string like "Pan to: typing activity detected".

### Dampened panning

Instead of centering the viewport directly on the activity target (which causes jarring jumps), the pan offset is computed as the **minimum shift** needed to keep the target visible within the zoomed viewport (with a 15% margin from the edge). At low zoom levels most screen positions are already visible and no panning is needed at all.

### Pipeline

```text
Per-sample velocity → Windowed scoring → Peak detection →
  Spatial-aware clustering (time + position) → Top-N by score →
  Chain consecutive clusters (within PAN_MERGE_GAP_MS) →
  Generate zoom-in at chain start, pan between clusters, zoom-out at chain end
```

Configurable via sensitivity presets (Low/Medium/High) which vary `max_clusters` and `min_gap_ms`.

---

## Video Export

`VideoExporter` (`app/video_exporter.py`) renders the final MP4 or GIF:

### Export Pipeline

```text
Source AVI → frame-by-frame decode (OpenCV) →
  compose static background + device bezel →
  apply zoom/pan (content-only or whole-canvas, depending on frame preset) →
  draw cursor overlay (virtual screen-rect mapping, clipped to screen area) →
  draw click ripple effects (virtual screen-rect mapping, clipped to screen area) →
  pipe to ffmpeg → MP4 (H.264, encoder selected at runtime, yuv420p)
                 → GIF  (palettegen + paletteuse filtergraph, 15 fps, loops forever)
```

### GIF export

When the output path ends in `.gif`, the exporter uses a palette-based GIF pipeline instead of the H.264 encoder chain. The ffmpeg filtergraph runs `fps=15,scale='min(iw,1920)':'min(ih,1080)':force_original_aspect_ratio=decrease,split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle` in a single pass. The `scale` step caps output at 1920×1080 (using `min()` expressions so sources smaller than that are never upscaled). The `GIF_FPS` constant (default `15`), `GIF_MAX_WIDTH` / `GIF_MAX_HEIGHT` constants (1920 / 1080), and `build_gif_args()` helper live in `app/utils.py`. The encoder fallback chain is not used for GIF exports.

### Encoder selection

`detect_available_encoders()` in `app/utils.py` probes ffmpeg at startup to discover which H.264 encoders are available on the current system. The function tests NVENC (NVIDIA), QuickSync (Intel), and AMF (AMD) by running a short encode and checking the exit code. `best_hw_encoder()` returns the fastest available GPU encoder, falling back to `libx264`.

The `ENCODER_PROFILES` dict in `app/utils.py` maps each encoder ID to its ffmpeg arguments (codec, quality flags, preset). HW encoder quality args are tuned to approximate the CRF 18 quality level of libx264. `build_encoder_args()` returns the ready-to-use arg list for any supported encoder.

The user's encoder choice is persisted via `QSettings` and restored on next launch. The editor panel's ⚙ settings menu exposes a **Video encoder** submenu listing available encoders with a checkmark on the active one. During export, the status bar displays the active encoder name (e.g., "Encoding with NVIDIA NVENC…").

### Encoder fallback

The exporter uses a **two-phase fallback chain** strategy that tries other available HW encoders before falling back to software:

1. **Immediate check** — after launching ffmpeg, the exporter sleeps 100 ms and polls the process. If it has already exited (e.g., driver issues or unsupported parameters), the exporter tries the next available HW encoder in priority order (NVENC → QuickSync → AMF). Only after all HW encoders are exhausted does it fall back to `libx264`.
2. **Mid-stream retry** — if the hardware encoder fails partway through encoding (broken pipe or `OSError`), the exporter catches the error and restarts the full encode, walking the same fallback chain from the next HW encoder down to `libx264`.

A warning is logged with the original ffmpeg stderr output. `VideoExporter` emits a `status = Signal(str)` that `MainWindow._on_export_status()` connects to — on each fallback attempt, the status bar is updated with the display name of the encoder being tried (e.g., "Encoder fallback: trying Intel QuickSync…", then "Encoder fallback: using libx264…"). On Windows, pipe writes to a dead ffmpeg process may raise `OSError(22, 'Invalid argument')` instead of `BrokenPipeError`; both are caught gracefully.

### Export parameters

| Parameter | Default value |
| --------- | ------------- |
| Codec | H.264 — auto-selected GPU encoder or libx264 fallback |
| Quality | CRF 18 equivalent (tuned per encoder) |
| Preset | medium (software) / p4 or equivalent (hardware) |
| Pixel format | yuv420p |
| Pipe method | Raw frames via stdin |

The export runs in a background thread with progress signals emitted to the UI.

### Trimming

The exporter accepts optional `trim_start_ms` and `trim_end_ms` parameters. When set, frames before the trim start are skipped (`continue`) and frames after the trim end cause an early exit (`break`). The total frame count and progress reporting are adjusted to reflect only the trimmed duration.

---

## Compositor

Two compositor implementations exist for different contexts:

| Compositor | Technology | Used by |
| ---------- | --------- | ------- |
| `compositor.py` | QPainter (Qt) | Live preview widget |
| `video_exporter.py` (inline) | NumPy + OpenCV | Video export |

Both produce identical output: gradient background → device bezel (rounded rect with edge highlights) → screen content (zoomed/panned) → cursor + click effects.

Zoom behavior is **conditional on the active frame preset**:

- **No Frame**: zoom/pan applies only to the video content inside the screen area — background stays static. Cursor and click overlays use virtual screen-rect mapping: their positions are transformed into the zoomed coordinate space and clipped to the screen area.
- **Device frame (any bezel)**: zoom/pan moves the device (frame + video) while the background stays static — like physically bringing a device closer and moving it around. The background gradient/pattern is always visible and never zooms.

### Preview canvas sizing

The preview widget sizes its canvas based on the selected output dimensions. The compositor's `compose_scene` is called with `(canvas_w, canvas_h)` instead of the full widget dimensions, and the painter is translated and clipped to the canvas rect.

- **Auto (source)**: The canvas is letterboxed or pillarboxed to match the source video's native aspect ratio.
- **Non-auto presets** (e.g., 1:1, 4:3, 9:16): The compositor renders at the target aspect ratio with the device frame fitted and centered within it, giving an accurate preview of the export result.

This replaces the previous scrim-overlay approach where the full scene was rendered at widget size and a semi-transparent dark overlay was drawn over margin areas.

---

## Input Tracking

### Mouse tracker

`MouseTracker` uses a `QTimer` at 60 Hz to poll `QCursor.pos()`. Simple and reliable — no hooks needed for position tracking.

### Keyboard tracker

`KeyboardTracker` installs a **Win32 low-level keyboard hook** (`WH_KEYBOARD_LL`) via `ctypes`. Only timestamps are recorded — no key identities, for privacy.

**Critical:** Uses `WINFUNCTYPE` (not `CFUNCTYPE`) for 64-bit Windows compatibility. Hook callbacks have explicit `argtypes` and `restype` to prevent integer overflow on 64-bit pointers.

### Click tracker

`ClickTracker` installs a **Win32 low-level mouse hook** (`WH_MOUSE_LL`) to detect left/right clicks. Records position + timestamp.

### Hook safety

All hooks run in dedicated threads with their own Win32 message loops. `CallNextHookEx` is always called to avoid blocking other applications. Hook threads append events directly to a shared list (CPython GIL ensures thread-safe `list.append`) instead of using cross-thread Qt signals, preventing event loss from unprocessed signal queues. Hook callbacks are wrapped in `try/except` to prevent exceptions from crashing the hook thread.

---

## UI Architecture

### Frameless window

The app uses `Qt.WindowType.FramelessWindowHint` with a custom `TitleBar` widget that handles:

- Drag-to-move
- Double-click to maximize/restore
- Minimize / maximize / close buttons
- **↩ New Recording** button — visible only in edit view; calls `_discard_recording()` in `MainWindow`, which resets all session state and returns to the record view
- Export button

### Theme

`DARK_THEME` in `app/theme.py` is a comprehensive QSS stylesheet (~200 lines). All styling is done via QSS, not QPalette manipulation (palette provides minimal base colors only).

### Widget communication

All inter-component communication uses Qt **signals and slots**:

```text
EditorPanel.output_dimensions_changed → MainWindow._on_output_dim_changed → PreviewWidget.set_output_dim
TimelineWidget.segment_clicked → MainWindow._on_segment_clicked → context menu
PreviewWidget.zoom_at_requested → MainWindow._on_preview_zoom_at → _add_keyframe
```

### Threading model

| Thread | Purpose |
| ------ | ------- |
| Main (GUI) thread | All Qt widgets, painting, event handling |
| Recording thread | Frame capture loop (WGC/GDI → ffmpeg pipe) |
| Keyboard hook thread | Win32 `WH_KEYBOARD_LL` message loop |
| Click hook thread | Win32 `WH_MOUSE_LL` message loop |
| Export thread | Frame-by-frame render + ffmpeg pipe |
| Hotkey thread | Win32 `RegisterHotKey` + `GetMessage` loop |
| Thumbnail threads | Background thumbnail generation for source picker |
| `_LoadProjectWorker` | Background ZIP extraction and session deserialization when loading `.fcproj` files |

---

## Processing Overlay

`ProcessingOverlay` (`app/widgets/processing_overlay.py`) is a full-window pulsing banner used to block interaction and provide feedback during long-running operations. It is **reusable** — the `show_overlay(title, subtitle)` method accepts configurable text, so the same widget serves multiple contexts:

| Context | Title | Subtitle |
| ------- | ----- | -------- |
| Finalizing a recording | "Processing…" | "Finalizing your recording" |
| Loading a project file | "Loading project…" | "Extracting and restoring session" |

When loading a `.fcproj` file, the heavy work (ZIP extraction, JSON deserialization, AVI copy) runs on a background `_LoadProjectWorker(QThread)` so the UI stays responsive. The overlay is shown before the worker starts and hidden when it emits its `finished` signal.

---

## Logging

All diagnostic output uses Python's `logging` module instead of bare `print()` calls. Each module creates a module-level logger:

```python
import logging
logger = logging.getLogger(__name__)
```

`logging.basicConfig()` is configured in `main.py` with:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s | %(levelname)s | %(message)s",
)
```

This provides consistent, filterable output with the originating module name and severity level in every log line.

---

## Project Files

`.fcproj` files are ZIP archives containing:

```text
project.fcproj (ZIP)
├── project.json    — session metadata (mouse track, keyframes, settings)
└── recording.avi   — raw lossless intermediate video
```

The JSON includes:

- Recording session data (mouse positions, key events, click events, zoom keyframes)
- Monitor geometry
- Actual FPS
- Background and frame preset names

---

## Build & Distribution

### PyInstaller

`build.bat` produces a single-folder distribution:

```text
dist/FollowCursor/
├── FollowCursor.exe
├── PySide6/          (only QtCore, QtGui, QtWidgets, QtSvg)
├── cv2/
├── numpy/
└── ...
```

40+ unused PySide6 modules are explicitly excluded (QtWebEngine, Qt3D, QtMultimedia, QtQml, etc.) to keep the distribution small.

### CI/CD

GitHub Actions (`.github/workflows/build.yml`):

- Triggers on push/PR to `main` and on `v*` tags
- Extracts version from `app/version.py`
- Builds with PyInstaller on `windows-latest`
- Uploads versioned artifact
- Creates GitHub Release on version tags

---

## Key Design Decisions

### DPI awareness

PySide6 automatically sets `PER_MONITOR_DPI_AWARE_V2`. **Never** call `SetProcessDpiAwareness` manually — it would conflict with Qt's own handling.

### No compositor during recording

During recording, the preview widget shows a **static blurred snapshot** instead of live compositor output. This avoids doubling the GPU/CPU work and keeps frame capture at full speed.

### Wall-clock playback

Video playback uses `time.perf_counter()` anchored at play-start, not QTimer tick counting. This eliminates:

- Timer interval rounding drift (`int(1000/60) = 16` instead of 16.67)
- Frame position off-by-one from OpenCV's `CAP_PROP_POS_FRAMES` returning the next frame index

### Clean shutdown

`closeEvent` calls `os._exit(0)` to avoid Qt cleanup hangs caused by native Win32 hooks still holding threads.

### Error resilience

- **Global exception handler:** `sys.excepthook` is set in `main.py` to log unhandled exceptions via the `logging` module instead of crashing silently.
- **Recording guards:** `_do_start_recording()` and `_stop_recording()` are wrapped in `try/except` — failures are logged and the UI is restored to a usable state.
- **Finalize guard:** `_on_finalize_done()` catches exceptions from post-recording processing and hides the processing overlay gracefully.
- **Hook callbacks:** Win32 hook callbacks in `click_tracker.py` and `keyboard_tracker.py` wrap their logic in `try/except` to prevent a crash from tearing down the hook thread.
- **Export pipe errors:** Both `BrokenPipeError` and `OSError` are caught when writing to the ffmpeg pipe (Windows raises `OSError(22)` instead of `BrokenPipeError`).
- **Encoder fallback chain:** If a hardware encoder fails, the exporter tries the next available HW encoder in priority order before falling back to `libx264`.

### Frame preset naming

Frame presets use generic names (Wide Bezel, Slim Bezel) — never trademarked device names.
