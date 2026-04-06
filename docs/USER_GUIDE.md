# FollowCursor — User Guide

A comprehensive reference for every feature in FollowCursor.

---

## Table of Contents

1. [Overview](#overview)
2. [Recording](#recording)
   - [Choosing a Source](#choosing-a-source)
   - [Countdown & Start](#countdown--start)
   - [During Recording](#during-recording)
   - [Stopping a Recording](#stopping-a-recording)
3. [Playback & Timeline](#playback--timeline)
   - [Preview Window](#preview-window)
   - [Timeline Tracks](#timeline-tracks)
   - [Seeking & Playback Controls](#seeking--playback-controls)
4. [Zoom System](#zoom-system)
   - [Smart Auto-Zoom](#smart-auto-zoom)
   - [Manual Zoom Keyframes](#manual-zoom-keyframes)
   - [Editing Zoom Segments](#editing-zoom-segments)
   - [Zoom Depth Levels](#zoom-depth-levels)
   - [Centroid Editing](#centroid-editing)
   - [Live Zoom During Recording](#live-zoom-during-recording)
5. [Click Events](#click-events)
   - [Click Track](#click-track)
   - [Click Selection & Deletion](#click-selection--deletion)
   - [Click Ripple Effects](#click-ripple-effects)
6. [Visual Customization](#visual-customization)
   - [Background Presets](#background-presets)
   - [Device Frames](#device-frames)
   - [Output Dimensions](#output-dimensions)
7. [Video Export](#video-export)
   - [Export Settings](#export-settings)
   - [What Gets Rendered](#what-gets-rendered)
8. [Trimming](#trimming)
9. [Segment Deletion](#segment-deletion)
10. [Undo & Redo](#undo--redo)
11. [Project Files](#project-files)
    - [Saving a Project](#saving-a-project)
    - [Loading a Project](#loading-a-project)
12. [Open in Clipchamp](#open-in-clipchamp)
13. [Keyboard Shortcuts](#keyboard-shortcuts)
14. [UI Reference](#ui-reference)
    - [Title Bar](#title-bar)
    - [Editor Panel](#editor-panel)
    - [Preview Widget](#preview-widget)
    - [Timeline Widget](#timeline-widget)
    - [Recording Border](#recording-border)
    - [Settings Menu](#settings-menu)

---

## Overview

FollowCursor is a Windows screen recorder that creates polished, cinematic tutorial videos. It records your screen or a specific window, tracks your mouse, keyboard, and click activity, then lets you add smooth zoom-and-pan effects that follow your cursor. The exported MP4 looks like a professionally edited screencast — with the camera gliding from one area of interest to the next.

**Typical workflow:**

1. Pick a screen or window to capture
2. Record your demo or tutorial
3. Add zoom keyframes (automatically or manually)
4. Customize the background and device frame
5. Export a polished MP4

---

## Recording

### Choosing a Source

Click **Select Source** in the sidebar to open the Source Picker dialog. Two tabs are available:

| Tab | What it captures | Method |
| --- | ---------------- | ------ |
| **Screens** | An entire monitor | Windows Graphics Capture (hardware-accelerated) with GDI fallback |
| **Windows** | A single application window | Win32 PrintWindow (no bleed-through from overlapping windows) |

Each option shows a live thumbnail preview so you can confirm the correct source before starting.

- **Monitor capture** records the full display at native resolution. On multi-monitor setups, each monitor is listed separately.
- **Window capture** records only that window's content, regardless of whether it's obscured by other windows.

### Countdown & Start

After clicking **Start Recording**, a **3-second countdown** overlay (3 → 2 → 1) appears on top of the preview. This gives you time to switch to the target application before recording begins.

Once the countdown completes:

- The app minimizes to the **system tray**
- Recording starts immediately at **30 fps**
- Input tracking begins (mouse, keyboard, clicks)

### During Recording

While recording is active:

- **Mouse position** is sampled at 60 Hz
- **Keyboard events** (timestamps only — no key identities, for privacy) are recorded
- **Click events** (position + timestamp) are recorded
- A **red pulsing border** appears around the captured monitor to indicate recording is in progress (monitor capture only)
- The preview shows a **static blurred snapshot** of the last captured frame to conserve CPU

**Live zoom hotkeys** are available during recording — see [Live Zoom During Recording](#live-zoom-during-recording).

### Stopping a Recording

Stop recording using any of these methods:

- Press **Ctrl+Shift+R** (global hotkey — works from any application)
- Right-click the **system tray icon** → **Stop Recording**

The app restores from the tray and switches to the editing view, with the recorded video loaded in the timeline.

A prominent **processing overlay** appears over the app while the recording is being finalized (thread cleanup, video remuxing). The overlay disappears automatically when the video is ready for editing.

---

## Playback & Timeline

### Preview Window

The preview widget shows your recorded video with all zoom, pan, background, and device frame effects applied in real time. What you see in the preview is exactly what will be exported.

- The canvas is sized to match the selected output aspect ratio (letterboxed/pillarboxed for "Auto", or fitted to the target preset)
- During playback, frames are rendered through the compositor pipeline (background → device frame → zoomed/panned video → cursor overlay)

### Timeline Tracks

The timeline displays multiple synchronized tracks:

| Track | What it shows |
| ----- | ------------- |
| **Mouse heatmap** | A color strip showing mouse movement speed over time — hotter colors indicate faster movement, cooler colors indicate slower or stationary cursor |
| **Keyboard track** | Tick marks showing when keystrokes occurred |
| **Click track** | Dots marking individual mouse click events |
| **Zoom segments** | Gradient-colored blocks showing where zoom keyframes are active. A taller segment means a higher zoom level |

### Seeking & Playback Controls

- **Click anywhere** on the timeline to seek to that point in the video
- **Play/Pause** button (or **Space** bar) to start or stop playback
- **Skip to start** (⏮) and **Skip to end** (⏭) buttons for quick navigation
- A vertical playhead line indicates the current position
- Wall-clock-based playback timing ensures smooth, accurate video playback regardless of frame rendering speed

---

## Zoom System

The zoom system is the core of FollowCursor. It creates smooth, cinematic camera movements that follow your cursor from one point of interest to the next.

### Smart Auto-Zoom

The **Activity Analyzer** can automatically generate zoom keyframes from your recorded input data. It detects two types of activity:

| Activity Type | How it's detected | Result |
| ------------- | ----------------- | ------ |
| **Typing bursts** | Mouse is stationary while keyboard events fire | Zoom into the typing area (uses keystroke cursor position when available) |
| **Click clusters** | One or more clicks occur within a short time window | Zoom into the click region (highest priority) |

Clicks are weighted slightly higher than typing — a deliberate click is treated as the strongest signal. Even a single click will generate a zoom event. Mouse settlements (cursor resting) do **not** trigger zoom events.

The analyzer uses **spatial-aware clustering** — clicks and typing events that happen in the same area of the screen are merged into a single sustained zoom instead of creating repeated zoom-out/zoom-in cycles. When consecutive clusters occur within 3 seconds of each other, they are grouped into **chains** — the camera zooms in at the first cluster, pans smoothly to each subsequent cluster while staying zoomed, then zooms out only after the last cluster. The viewport **centers** on the activity target (typing field or click location), clamped so the viewport stays within source bounds.

**To use Smart Auto-Zoom:**

1. Open the **Editor Panel** (right sidebar)
2. Find the **SMART ZOOM** section
3. Choose a sensitivity level:
   - **Low** — up to 3 zoom clusters, 6-second minimum gap between them
   - **Medium** — up to 6 clusters, 4-second gap
   - **High** — up to 10 clusters, 2.5-second gap
4. Click **✨ Auto-generate zoom keyframes**
5. If you already have zoom sections, a confirmation dialog asks whether to **Replace** them or **Cancel**

The generated keyframes appear as color-coded segments on the timeline.

### Manual Zoom Keyframes

Add zoom keyframes by hand for precise control:

- **Right-click the preview** — **🔍  Add Zoom here** — adds a keyframe at the clicked position and the current playback time
- **Right-click the timeline** (empty space) — **🔍  Add Zoom here** — adds a zoom section centered on the recorded cursor position at that time
- **Editor Panel** → **🔍 Add Zoom** — adds a keyframe at the current playback position, centered on the cursor's recorded location at that time

Each keyframe stores:

- **Timestamp** — when the zoom begins
- **Position (x, y)** — the normalized pan center (where the camera points)
- **Zoom level** — magnification scale
- **Duration** — length of the zoom-in transition (default 400 ms)
- **Reason** — a label describing why the keyframe exists (e.g., "Mouse activity burst", "Click cluster", "Manual")

### Editing Zoom Segments

On the timeline, zoom keyframes appear as colored segments. You can interact with them:

- **Click a segment** to select it (highlighted with a brighter border)
- **Press Delete or Backspace** to remove the selected zoom segment
- **Drag a segment edge** (left or right) to resize the zoom duration
- **Drag the segment body** to move the entire zoom to a different time
- **Right-click a segment** to open the context menu with options:
  - Set depth (zoom level)
  - Set centroid (pan center)
  - Delete zoom section

### Zoom Depth Levels

Right-click a zoom segment and choose from four depth presets:

| Depth | Zoom Level | Best for |
| ----- | ---------- | -------- |
| **Subtle** | 1.25× | Gentle emphasis, large UI areas |
| **Medium** | 1.5× | Default, good for most content |
| **Close** | 2.0× | Focused detail, small UI elements |
| **Detail** | 2.5× | Maximum zoom, fine text or icons |

### Centroid Editing

The **centroid** is the point the camera focuses on during a zoom. To reposition it:

1. **Right-click** a zoom segment on the timeline
2. Select **📍 Set centroid**
3. The preview enters **centroid pick mode** — the cursor changes to a crosshair
4. **Click** the point on the preview where you want the camera to focus
5. The keyframe's pan center updates to match

The centroid coordinates (as a percentage of the frame) are displayed in the keyframe list in the editor panel.

### Pan Path Points

When a zoom segment is long, you can add **pan path points** to smoothly redirect the camera to different parts of the screen while staying zoomed in. Pan points create a panning path through the zoomed view.

**Adding a pan point:**

1. While viewing a zoom segment in the preview, **right-click** on the video surface at the position you want the camera to pan to
2. Select **📌  Add pan point here** (only appears while zoomed in)
3. A numbered yellow circle marker appears on the timeline
4. The pan point's center is set to the clicked position on the video

**Editing pan points:**

- **Right-click** a pan point marker to open its context menu:
  - **📍 Pick center on preview** — enter centroid-pick mode to set where the camera points
  - **⬅ Move earlier / ➡ Move later** — reorder pan points by swapping their timestamps
  - **🗑 Delete pan point** — remove the pan point
- **Drag** a pan point marker horizontally to change its timestamp within the segment

Pan points are numbered sequentially (1, 2, 3…) to show their order. During export and playback, the zoom engine smoothly interpolates between consecutive pan points using ease-out transitions.

### Live Zoom During Recording

While recording, you can add zoom keyframes in real time using global hotkeys:

| Hotkey | Action |
| ------ | ------ |
| **Ctrl+Shift+=** | Zoom in at the current cursor position |
| **Ctrl+Shift+-** | Zoom back out to 1.0× (no zoom) |

These hotkeys work from any application — you don't need to switch back to FollowCursor.

### Zoom Transitions

All zoom and pan transitions use **cubic ease-out** easing ($1 - (1-t)^3$) — a fast start that decelerates asymptotically to zero, producing a natural "glide to a stop" feel. The default transition duration is 400 ms.

### Pan-While-Zoomed

When Smart Auto-Zoom detects consecutive activity clusters that are close in time (within 3 seconds of each other), the camera **stays zoomed in** and smoothly pans from one cluster to the next, instead of zooming out and back in between them. This eliminates jarring zoom-out → zoom-in cycles and produces a cinematic "follow the action" effect.

- Pan duration is proportional to the screen distance between clusters (400 ms–700 ms range)
- The same ease-out curve is used for panning, so the camera decelerates smoothly into each new position
- Chains are capped at **4 clusters** — if more consecutive clusters exist, a new chain starts
- The camera only zooms out after the last cluster in the chain

---

## Click Events

### Click Track

Mouse clicks are recorded with position and timestamp. They appear as small dots on the **click track** row of the timeline.

### Click Selection & Deletion

- **Left-click** a click event dot on the timeline to select it (highlighted)
- Press **Delete** to remove the selected click event
- This is useful for cleaning up accidental or unwanted clicks before export

### Click Ripple Effects

During export, clicks are rendered as animated **ripple effects** — concentric circles that expand outward from the click position. This visually highlights to viewers where you clicked, making tutorials easier to follow.

---

## Visual Customization

### Background Presets

The background fills the area behind and around the device frame. Choose from **84 presets** in the editor panel, organized into three categories via a dropdown selector:

#### Solid (39)

Every colour from the palette as a flat fill. Includes lights (Pure White, Light Blue, …), mids (Yellow, Teal, …), and darks (Dark Purple, Blue Black, …).

#### Gradient (37)

Smooth blends within a colour family, with three sub-types:

| Sub-type | Count | Look |
| -------- | ----- | ---- |
| **Linear** | 20 | Vertical blend from light to dark (11 Light→Dark + 9 Mid→Dark "Deep") |
| **Radial** | 11 | Concentric glow radiating from the centre on a dark fill |
| **Spotlight** | 6 | Off-centre glow from the upper-right corner on a dark fill |

#### Pattern (8)

| Sub-type | Count | Look |
| -------- | ----- | ---- |
| **Wavy** | 8 | Organic sine-wave layers over a gradient base |

Use the category dropdown (Solid / Gradient / Pattern) above the swatch grid to switch between groups. Click a swatch to apply it — the preview updates immediately.

### Device Frames

Device frames add a bezel (border) around the recorded content, simulating a monitor or device screen. Choose from **5 presets**:

| Frame | Look | Details |
| ----- | ---- | ------- |
| **Wide Bezel** | Thick dark border with camera dot | 28 px bezel, rounded corners, drop shadow |
| **Slim Bezel** | Thinner dark border with camera dot | 18 px bezel, rounded corners, drop shadow |
| **Thin Border** | Minimal dark edge | 6 px bezel, no camera dot, subtle shadow |
| **Shadow Only** | No border, floating shadow | No bezel, rounded corners, drop shadow only |
| **No Frame** | Clean, edge-to-edge video | No bezel, no shadow, no padding |

### Output Dimensions

Control the aspect ratio and resolution of the exported video:

| Preset | Resolution | Use case |
| ------ | ---------- | -------- |
| **Auto (source)** | Matches recording resolution | Default — no cropping or padding |
| **16:9** | 1920 × 1080 | Standard widescreen, YouTube |
| **3:2** | 1620 × 1080 | Tablets, some laptops |
| **4:3** | 1440 × 1080 | Classic presentation format |
| **1:1** | 1080 × 1080 | Social media (Instagram) |
| **9:16** | 1080 × 1920 | Vertical video (TikTok, Reels, Shorts) |

The preview accurately reflects the export output:

- **Auto (source)**: The canvas is letterboxed or pillarboxed to match the source video's native aspect ratio.
- **Non-auto presets** (e.g., 1:1, 4:3, 9:16): The compositor renders at the target aspect ratio with the device frame fitted and centered within it, giving you an accurate preview of exactly what the export will look like.

---

## Video Export

### Recording Pipeline

FollowCursor uses a **H.264 intermediate codec** (CRF 18, ultrafast preset) for buffering recorded frames during capture. This significantly reduces temporary disk usage:

- **Traditional lossless approach (huffyuv):** ~50 GB/min for 4K recordings
- **FollowCursor H.264 intermediate:** Under 1 GB/min for 4K recordings

The intermediate video is not your final export — it's just efficient buffering. During export, the entire pipeline (zoom, pan, cursor, effects) is applied and re-encoded with your chosen final quality settings. You control the final output quality via the Video Encoder settings (see [Video Encoder](#video-encoder) below).

This approach frees up disk space during recording while maintaining full editing capability, and the re-encoding during export ensures professional output quality.

### Export Settings

Click **⬆ Export** in the title bar to start an export. You'll be asked to choose a destination folder, filename, and format.

Two export formats are available:

| Format | Extension | Best for |
| ------ | --------- | -------- |
| **MP4 Video** | `.mp4` | Sharing, uploading to platforms, embedding in presentations |
| **GIF Animation** | `.gif` | Embedding in GitHub READMEs, Markdown docs, Slack, and other inline-image contexts |

#### MP4 export settings

- **Codec:** H.264 — hardware-accelerated when available (see [Video Encoder](#video-encoder) below), software `libx264` as fallback
- **Quality:** CRF 18 equivalent (HW encoders use tuned quality parameters to match)
- **Pixel format:** yuv420p (maximum compatibility)
- **Preset:** medium (balanced speed/compression)

#### GIF export settings

- **Frame rate:** 15 fps (optimised for size/quality balance)
- **Colours:** 256-colour palette generated per export using `palettegen` (diff mode) for maximum colour accuracy
- **Dithering:** Bayer dithering (scale 5, diff mode) to reduce colour banding
- **Loop:** Loops forever (`-loop 0`)

For both formats, frames are piped directly to ffmpeg via stdin — no temporary files are written to disk.

> **Note:** GIF files can be significantly larger than MP4 for the same content. If file size matters, prefer MP4 or reduce the output resolution via the **OUTPUT SIZE** picker before exporting.

### Video Encoder

FollowCursor automatically detects GPU-accelerated H.264 encoders on your system and selects the best one on first launch:

| Encoder | GPU vendor | Notes |
| ------- | ---------- | ----- |
| **NVENC** (`h264_nvenc`) | NVIDIA | Fastest; requires a GeForce/Quadro GPU |
| **QuickSync** (`h264_qsv`) | Intel | Available on most Intel CPUs with integrated graphics |
| **AMF** (`h264_amf`) | AMD | Available on Radeon GPUs |
| **Software** (`libx264`) | Any | CPU-based fallback; always available |

To change the encoder, open the **⚙ Settings** menu in the editor panel and select **Video encoder** → choose from the list of detected encoders. A checkmark indicates the current selection. Your choice is saved automatically and restored on next launch.

Hardware encoding is significantly faster than software encoding and offloads work from the CPU to the GPU, with quality tuned to approximate CRF 18. FollowCursor uses a **two-phase encoder fallback chain** to ensure exports always succeed:

1. **Immediate check** — if ffmpeg exits within 100 ms of launch (e.g., driver issues or unsupported parameters), the exporter tries the next available HW encoder in priority order (NVENC → QuickSync → AMF) before falling back to Software (libx264).
2. **Mid-stream retry** — if the hardware encoder fails partway through (broken pipe or OS error), the exporter restarts the entire encode, walking the same fallback chain from the next HW encoder down to libx264.

For example, if NVIDIA NVENC fails, the exporter will try Intel QuickSync next, then AMD AMF, then finally libx264. On each fallback attempt, the status bar updates to show which encoder is being tried (e.g., "Encoder fallback: trying Intel QuickSync…"). During normal export, it shows which encoder is actively being used (e.g., "Encoding with NVIDIA NVENC…").

### What Gets Rendered

Every frame of the export includes all of the following (composited in order):

1. **Background** — the selected gradient or solid fill
2. **Device frame** — bezel, shadow, and camera dot
3. **Video content** — the recorded frame, zoomed and panned according to active keyframes
4. **Cursor overlay** — a rendered arrow cursor at the recorded mouse position
5. **Click ripples** — animated expanding circles at click positions

Zoom behavior depends on the active **frame preset**:

- **No Frame**: zoom/pan applies only to the video content inside the screen area — the background stays static. Cursor and click overlays are mapped to the zoomed screen rect and clipped to the screen area.
- **Device frame (any bezel)**: zoom/pan moves the device (frame + video) while the background stays static — like physically bringing a device closer and moving it around. The background gradient/pattern is always visible and never zooms.

Export progress is shown in the title bar's Export button.

If the timeline has **trim handles** set, only the trimmed portion of the recording is exported — frames outside the trim range are skipped.

---

## Trimming

Trim your recording to remove unwanted content at the start or end without re-recording.

### Trim Handles

The timeline has **trim handles** (yellow bars) at both edges. Drag them to adjust the trim range:

- **Left handle** — sets the trim start point (content before this is excluded)
- **Right handle** — sets the trim end point (content after this is excluded)

After trimming, the timeline viewport shows **only the content between the trim start and trim end**. All trimmed-out regions are hidden from view. Time markers re-index to start at **0:00** from the trim start, and the total duration display reflects the trimmed length.

### Playback Behavior

- Playback is confined to the trimmed range — the playhead cannot move outside it
- Seeking, skipping to start/end, and clicking on the timeline all respect the trim boundaries
- When playback reaches the trim end, it pauses automatically
- Pressing play when paused at the trim end wraps back to the trim start

### Visible Content

Zoom segments, voiceover segments, activity heatmaps (mouse, keyboard, clicks), and click event markers that fall outside the trimmed range are hidden from the timeline.

### Untrimming

Drag the trim handles back outward to restore previously hidden content:

- **Left handle** — drag leftward to reveal content before the current trim start, down to the beginning of the recording
- **Right handle** — drag rightward to reveal content after the current trim end, up to the full recording duration

### Reset Trim

Right-click on either trim handle and select **↩ Reset trim** to reset both handles to the full recording range in one step.

### Constraints

- The trimmed region must be at least **500 ms** long
- Trim handles snap to the edges of existing zoom segments for convenience
- Trim values are **saved with the project** and restored when loading a `.fcproj` file

### Effect on Export

When trim handles are set, the export only renders frames within the trimmed range. Frames before the trim start and after the trim end are skipped entirely, producing a shorter video.

---

## Segment Deletion

After splitting a recording into segments, individual segments can be deleted to remove unwanted portions from the timeline and exported output.

### Deleting a Segment

- **Right-click** a video segment on the Clips track → select **Delete segment**
- **Left-click** a video segment to select it, then press **Delete** or **Backspace**

### Ripple Delete

When a segment is deleted, adjacent segments close the gap — the remaining segments are played and exported sequentially with no gap between them.

### Constraints

- At least **one segment must remain** — the last segment cannot be deleted
- Zoom keyframes and voiceover segments inside a deleted segment are removed automatically
- Segment deletion is **undoable** via **Ctrl+Z**

### Effect on Export

Deleted segments are excluded from the exported video. Only frames within remaining segments are rendered.

---

## Undo & Redo

All zoom keyframe, click event, and video segment changes can be undone and redone. The undo history supports up to **50 snapshots**.

### Supported Actions

Every zoom keyframe, click event, and trim mutation is tracked:

- Adding a keyframe (manual or auto-generated)
- Removing a keyframe
- Moving a keyframe (drag on timeline)
- Changing zoom depth
- Setting centroid
- Deleting a zoom section
- Auto-generating keyframes (the entire batch)
- Deleting a click event
- Deleting a video segment

### How to Undo/Redo

| Method | Undo | Redo |
| ------ | ---- | ---- |
| **Keyboard** | **Ctrl+Z** | **Ctrl+Shift+Z** or **Ctrl+Y** |
| **Buttons** | ↩ **Undo** button in editor panel | **Redo** ↪ button in editor panel |

---

## Project Files

### Saving a Project

Save your work to continue editing later:

- Use **Ctrl+S** or the save option in the UI
- The project is saved as a **`.fcproj`** file
- If you’ve previously saved the project, **Ctrl+S** saves to the same file without prompting
- **Incremental re-save**: when saving to an existing project file, only the metadata (keyframes, clicks, zoom settings, etc.) is updated — the video data is never read or copied, making re-saves near-instant regardless of video size
- The current project filename appears in the **title bar** (with a **●** dot indicator when there are unsaved changes)
- When you export, the default filename matches the project name (e.g., `MyProject.mp4` instead of a generic timestamp-based name)

A `.fcproj` file is actually a **ZIP archive** containing:

- The raw recorded video (lossless intermediate)
- All metadata (mouse positions, keyboard events, click events, zoom keyframes, trim range, background/frame settings, output dimensions)

### Loading a Project

Open a previously saved project:

- Use the open/load option in the UI
- Select a `.fcproj` file

While the project is loading, a **"Loading project…"** overlay appears over the app (the same pulsing banner used when finalizing a recording). The ZIP extraction and session restoration run in the background so the UI stays responsive. The overlay disappears automatically when the project is ready.

The entire recording session is restored, including all tracked input data and zoom keyframes, so you can resume editing exactly where you left off.

---

## Open in Clipchamp

For additional editing beyond what FollowCursor offers, you can hand off your recording to **Clipchamp** (Microsoft's built-in video editor on Windows 11):

- Click the **Clipchamp** button in the UI
- The exported video opens directly in Clipchamp for trimming, adding text overlays, transitions, or combining with other clips

---

## Keyboard Shortcuts

### Global Hotkeys (work from any application)

| Shortcut | Action |
| -------- | ------ |
| **Ctrl+Shift+R** | Start or stop recording |
| **Ctrl+Shift+=** | Zoom in at cursor position (during recording) |
| **Ctrl+Shift+-** | Zoom out to 1.0× (during recording) |

### Editor Shortcuts

| Shortcut | Action |
| -------- | ------ |
| **Space** | Play / Pause |
| **Z** | Insert zoom keyframe at playhead |
| **⏮ / ⏭** | Skip to start / end |
| **Delete** | Remove selected zoom segment, video segment, or click event |
| **Ctrl+Z** | Undo last zoom/click/segment change |
| **Ctrl+Shift+Z** | Redo last undone change |
| **Ctrl+Y** | Redo last undone change (alternate) |
| **Ctrl+S** | Save project |

### Mouse Interactions

| Interaction | Where | Action |
| ----------- | ----- | ------ |
| **Left-click** | Timeline | Seek to that time |
| **Left-click** | Zoom segment | Select segment |
| **Left-click** | Click event dot | Select click event |
| **Left-click** | Video segment | Select video segment |
| **Right-click** | Preview | Add zoom at click position |
| **Right-click** | Timeline (empty space) | Add zoom section at that time |
| **Right-click** | Zoom segment | Context menu (depth, centroid, delete) |
| **Right-click** | Video segment | Context menu (delete segment) |
| **Drag edge** | Zoom segment | Resize segment duration |
| **Drag body** | Zoom segment | Move segment in time |
| **Drag handle** | Timeline edge | Set trim start/end point |

---

## UI Reference

### Title Bar

A custom frameless title bar displaying:

- Application name, current project filename (if saved), and unsaved-changes indicator (●)
- Version number
- **Export** button — export the video (shows progress during export)
- Window controls (minimize, maximize, close)

When closing the app with unsaved changes, a confirmation dialog asks whether to **Save**, **Don’t Save**, or **Cancel**.

### Editor Panel

The right sidebar containing all editing controls, organized into sections:

- **ZOOM KEYFRAMES** — list of all zoom keyframes with timestamps, zoom levels, centroids, and reasons. Each row includes an action button for quick editing.
- **🔍 Add Zoom** — add a manual zoom keyframe at the current playback position
- **SMART ZOOM** — sensitivity selector (Low / Medium / High) and the auto-generate button
- **BACKGROUND** — category dropdown (Solid / Gradient / Pattern) + swatch grid for all 90 backgrounds
- **DEVICE FRAME** — clickable preset buttons for all 5 frame styles
- **OUTPUT SIZE** — dropdown for selecting aspect ratio / resolution
- **↩ Undo / Redo ↪** — buttons to undo or redo zoom keyframe and click event changes
- **⚙ Settings** — cog icon that opens a popup menu with additional options (e.g., toggle zoom debug overlay)

### Preview Widget

The central preview area showing:

- Live compositor output during playback (background + frame + zoomed video + cursor)
- Static blurred snapshot during recording (for performance)
- Crosshair cursor in centroid pick mode
- Right-click context menu for adding zoom keyframes

### Timeline Widget

The bottom timeline painted with QPainter, showing:

- Playhead position indicator
- Mouse speed heatmap (color-coded track)
- Keyboard event ticks
- Click event dots (selectable)
- Zoom segments (draggable, resizable, selectable, right-click context menu)
- **Trim handles** — draggable yellow bars at the timeline edges to set trim start/end points
- Dimmed overlay on trimmed-out regions
- Time ruler with markings

### Recording Border

A red pulsing border overlay that appears around the captured monitor during recording. Draws inside the monitor bounds so it doesn't bleed onto adjacent displays. Only shown for monitor capture (not window capture).

### Settings Menu

Click the **⚙** cog icon at the bottom of the editor panel (next to the ℹ️ session info label) to open the settings popup menu. Available settings:

- **Show zoom debug overlay** — Toggle colored markers on the preview showing where activity was detected and why zoom keyframes were placed. Useful for fine-tuning keyframe positions and verifying zoom transitions visually. **Enabled by default.**
- **🤖 AI Settings…** — Configure Azure AI Foundry credentials for AI-powered features (see [AI Features](#ai-features) below).
- **Video encoder** — Submenu listing all detected H.264 encoders (GPU-accelerated and software). A checkmark shows the current selection. See [Video Encoder](#video-encoder) for details.

---

## AI Features

FollowCursor includes optional AI-powered features that use **Azure AI Foundry** (Microsoft Foundry) models. These features require you to bring your own API credentials.

### Setup

1. Open **⚙ Settings** → **🤖 AI Settings…** in the editor panel
2. Enter your Azure AI Foundry **Endpoint** URL (e.g. `https://models.inference.ai.azure.com`)
3. Enter your **API Key** (or GitHub token for GitHub Models)
4. Enter your **Chat Model** deployment name (e.g. `gpt-4o-mini`) for AI zoom analysis and narration
5. Optionally enter a **TTS Model** deployment name (e.g. `tts-1`) for speech synthesis
6. Choose a **Voice** for TTS (alloy, echo, fable, onyx, nova, shimmer)
7. Click **OK** — settings are saved automatically

**Security Note:** Your API keys are encrypted using Windows DPAPI before being stored in the Windows Registry. They are decrypted on-demand when connecting to AI services and cleared from memory immediately after use. No plaintext credentials are written to disk.

### AI Smart Zoom

Instead of (or in addition to) the local activity analyzer, you can use an AI model to analyze your recording and generate zoom keyframes:

1. Record a session and switch to edit mode
2. In the **SMART ZOOM** section, click **🤖 AI Auto-generate zoom**
3. The AI receives a summary of your mouse movements, keystrokes, and clicks
4. It returns intelligent zoom sections targeting the most visually interesting moments
5. Results are applied the same way as local auto-zoom (replaces existing keyframes after confirmation)

The AI considers the narrative flow of your recording and creates well-paced zoom effects. Sensitivity and zoom depth settings apply the same as local auto-zoom.

**AI Response Limits**

To prevent excessive memory usage from malformed LLM responses, AI zoom analysis responses are capped at **50 zoom sections**. If the AI returns more than 50 sections, only the first 50 are applied. This limit ensures stable performance even with edge-case model outputs.

### Voiceover (Text-to-Speech)

Add voiceover segments at specific points in the timeline, write your text, and synthesize speech audio using Azure AI Foundry TTS:

**Adding a voiceover segment:**

- In the **VOICEOVER** section of the editor panel, click **🎙 Add Voiceover** — adds at the current playback position
- Or **right-click** anywhere on the timeline → **🎙 Add Voiceover here** — adds at that time

**Working with voiceover segments:**

1. A dialog appears where you enter the voiceover text and pick a voice
2. Click **Save** to store the segment (text only, no audio yet)
3. Click **🔊 Synthesize** to generate speech audio via Azure AI Foundry TTS immediately
4. Voiceover segments appear as teal blocks on the timeline's **Voice** track
5. **Click** a voiceover segment on the timeline to edit its text, change the voice, re-synthesize, or delete it

**During export:**

- All synthesized voiceover segments are merged into a single audio track
- Each segment plays at its timeline position in the exported video
- Multiple overlapping segments are mixed together automatically
- Audio is encoded as AAC at 192 kbps

> **Note:** Voiceover audio is only included in MP4 exports, not GIF exports. Segments without synthesized audio (gray blocks) are skipped during export.
