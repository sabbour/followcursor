# User Guide

A comprehensive reference for every feature in FollowCursor.

---

## Overview

FollowCursor is a Windows screen recorder that creates polished, cinematic tutorial videos. It records your screen or a specific window, tracks your mouse, keyboard, and click activity, then lets you add smooth zoom-and-pan effects that follow your cursor. The exported MP4 or GIF looks like a professionally edited screencast — with the camera gliding from one area of interest to the next.

**Typical workflow:**

1. Pick a screen or window to capture
2. Record your demo or tutorial
3. Add zoom keyframes (automatically or manually)
4. Customize the background, device frame, and visual overlays
5. Export a polished MP4 or GIF

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
- **Window capture** records only that window's content, regardless of whether it is obscured by other windows.

### Countdown & Start

After clicking **Start Recording**, a **3-second countdown** overlay (3, 2, 1) appears on top of the preview. This gives you time to switch to the target application before recording begins.

Once the countdown completes:

- The app minimizes to the **system tray**
- Recording starts immediately
- Input tracking begins (mouse at 60 Hz, keyboard events with cursor position, click events with position)

### During Recording

While recording is active:

- **Mouse position** is sampled at 60 Hz via QTimer polling
- **Keyboard events** (timestamps + cursor position) are recorded via a Win32 low-level hook
- **Click events** (position + timestamp) are recorded via a Win32 low-level mouse hook
- A **red pulsing border** appears around the captured monitor (monitor capture only)
- The preview shows a **static blurred snapshot** of the last captured frame to conserve CPU

**Live zoom hotkeys** are available during recording — see [Live Zoom During Recording](#live-zoom-during-recording).

### Stopping a Recording

Stop recording using any of these methods:

- Press **Ctrl+Shift+R** (global hotkey — works from any application)
- Right-click the **system tray icon** and select **Stop Recording**

The app restores from the tray and switches to the editing view with the recorded video loaded in the timeline. A **processing overlay** appears while the recording is being finalized and disappears when the video is ready.

---

## Playback & Timeline

### Preview Window

The preview widget shows your recorded video with all zoom, pan, background, device frame, annotations, cursor, click effects, and keystroke overlay applied in real time. What you see in the preview is exactly what will be exported.

The canvas is sized to match the selected output aspect ratio.

### Timeline Tracks

The timeline displays multiple synchronized tracks:

| Track | What it shows |
| ----- | ------------- |
| **Mouse heatmap** | Color strip showing mouse movement speed — hotter colors = faster movement |
| **Keyboard track** | Tick marks showing when keystrokes occurred |
| **Click track** | Dots marking individual mouse click events |
| **Clips track** | Video segments (after splitting) |
| **Zoom segments** | Gradient-colored blocks showing where zoom keyframes are active |
| **Voice track** | Teal pill-shaped blocks for voiceover segments |
| **Chapter markers** | Flag markers at detected scene boundaries |

### Seeking & Playback Controls

- **Click anywhere** on the timeline to seek to that point
- **Space** to play/pause
- **Skip to start/end** buttons for quick navigation
- A vertical playhead line indicates the current position

---

## Zoom System

The zoom system is the core of FollowCursor. It creates smooth, cinematic camera movements that follow your cursor from one point of interest to the next.

### Smart Auto-Zoom

The **Activity Analyzer** automatically generates zoom keyframes from your recorded input data. It detects two types of activity:

| Activity Type | How it is detected | Result |
| ------------- | ------------------ | ------ |
| **Typing bursts** | Mouse is stationary while keyboard events fire | Zoom into the typing area (uses keystroke cursor position when available) |
| **Click clusters** | One or more clicks occur within a short time window | Zoom into the click region (highest priority) |

Clicks are weighted higher than typing — a deliberate click is treated as the strongest signal. Even a single click generates a zoom event.

The analyzer uses **spatial-aware clustering** — clicks and typing events in the same area are merged into a single sustained zoom. When consecutive clusters occur close together, they are grouped into **chains** (up to 4 per chain) — the camera zooms in at the first cluster, pans smoothly to each subsequent cluster while staying zoomed, then zooms out only after the last cluster.

**To use Smart Auto-Zoom:**

1. Open the **Editor Panel** (right sidebar)
2. Find the **SMART ZOOM** section
3. Choose a sensitivity level:
    - **Low** — up to 3 zoom clusters, 6-second minimum gap
    - **Medium** — up to 6 clusters, 4-second gap
    - **High** — up to 10 clusters, 2.5-second gap
4. Click **Auto-generate zoom keyframes**
5. If you already have zoom sections, a confirmation dialog asks whether to **Replace** or **Cancel**

### AI Smart Zoom

Instead of (or in addition to) the local activity analyzer, you can use an AI model to analyze your recording and generate zoom keyframes:

1. Configure your Azure AI Foundry credentials in **Settings > AI Settings**
2. In the **SMART ZOOM** section, click **AI Auto-generate zoom**
3. The AI receives a summary of your mouse movements, keystrokes, and clicks
4. It returns intelligent zoom sections targeting the most visually interesting moments
5. Results are applied the same way as local auto-zoom

The AI considers the narrative flow of your recording and creates well-paced zoom effects like a professional cameraman. Responses are capped at **50 zoom sections** for stability.

### Manual Zoom Keyframes

Add zoom keyframes by hand for precise control:

- **Right-click the preview** — adds a keyframe at the clicked position and the current playback time
- **Right-click the timeline** (empty space) — adds a zoom section at that time
- **Press Z** — inserts a keyframe at the playhead, centered on the cursor position
- **Editor Panel** click **Add Zoom** — adds at the current playback position

### Editing Zoom Segments

On the timeline, zoom keyframes appear as colored segments:

- **Click a segment** to select it
- **Press Delete** to remove it
- **Drag a segment edge** to resize the zoom duration
- **Drag the segment body** to move it to a different time
- **Right-click a segment** for the context menu:
    - Set depth (zoom level)
    - Set centroid (pan center)
    - Delete zoom section

### Zoom Depth Levels

Right-click a zoom segment and choose from four depth presets:

| Depth | Zoom Level | Best for |
| ----- | ---------- | -------- |
| **Subtle** | 1.25x | Gentle emphasis, large UI areas |
| **Medium** | 1.5x | Default, good for most content |
| **Close** | 2.0x | Focused detail, small UI elements |
| **Detail** | 2.5x | Maximum zoom, fine text or icons |

### Centroid Editing

The **centroid** is the point the camera focuses on during a zoom. To reposition it:

1. **Right-click** a zoom segment on the timeline
2. Select **Set centroid**
3. The preview enters centroid pick mode — the cursor changes to a crosshair
4. **Click** the point on the preview where you want the camera to focus
5. The keyframe's pan center updates to match

### Pan Path Points

When a zoom segment is long, you can add **pan path points** to smoothly redirect the camera to different parts of the screen while staying zoomed in.

**Adding a pan point:**

1. While viewing a zoom segment in the preview, **right-click** on the video surface
2. Select **Add pan point here** (only appears while zoomed in)
3. A numbered yellow circle marker appears on the timeline

**Editing pan points:**

- **Right-click** a pan point marker to:
    - **Pick center on preview** — reposition the camera target
    - **Move earlier / Move later** — reorder pan points
    - **Delete pan point** — remove it
- **Drag** a pan point marker horizontally to change its timestamp

Pan points are numbered sequentially (1, 2, 3...) to show their order. The zoom engine smoothly interpolates between them using ease-in-out transitions.

### Live Zoom During Recording

While recording, add zoom keyframes in real time using global hotkeys:

| Hotkey | Action |
| ------ | ------ |
| **Ctrl+Shift+=** | Zoom in at the current cursor position |
| **Ctrl+Shift+-** | Zoom back out to 1.0x |

These hotkeys work from any application.

### Zoom Transitions

All zoom and pan transitions use **quintic ease-out** easing — a fast start that decelerates smoothly to a stop. The default transition duration is 400 ms.

Pan-between-clusters transitions use **quintic ease-in-out** (smoothstep) for zero velocity at both endpoints.

---

## Click Events

### Click Track

Mouse clicks are recorded with position and timestamp. They appear as small dots on the **click track** row of the timeline.

### Click Selection & Deletion

- **Left-click** a click event dot to select it
- Press **Delete** to remove it
- Useful for cleaning up accidental clicks before export

### Click Effects

During export, clicks are rendered as animated visual effects. Choose from **8 presets** in the editor panel:

| Preset | Style | Description |
| ------ | ----- | ----------- |
| Subtle Purple | Ripple | Default — expanding purple circles |
| Bold Red | Ripple | High-visibility red ripple |
| Neon Cyan | Ripple | Bright cyan expanding circles |
| Minimal Gray | Ripple | Understated gray ripple |
| High Contrast Yellow | Ripple | Maximum visibility yellow |
| Clean White | Ripple | Clean white expanding circles |
| Soft Green | Ripple | Gentle green ripple |
| Invisible | — | No click effect rendered |

Each preset has configurable color, duration, and radius. Click effects highlight to viewers exactly where you clicked, making tutorials easier to follow.

---

## Visual Enhancements

### Background Presets

The background fills the area behind and around the device frame. Choose from **84 presets** organized into three categories:

**Solid (39)** — Flat fills in every color from the palette, from lights (Pure White, Light Blue) to darks (Dark Purple, Blue Black).

**Gradient (37)** — Smooth blends with three sub-types:

| Sub-type | Count | Look |
| -------- | ----- | ---- |
| **Linear** | 20 | Vertical blend from light to dark |
| **Radial** | 11 | Concentric glow radiating from the center |
| **Spotlight** | 6 | Off-center glow from the upper-right corner |

**Pattern (8)** — Organic sine-wave layers over a gradient base (wavy style).

Use the category dropdown (Solid / Gradient / Pattern) to switch between groups. Click a swatch to apply — the preview updates immediately.

### Device Frames

Device frames add a bezel around the recorded content, simulating a monitor or device screen. Choose from **5 presets**:

| Frame | Look | Details |
| ----- | ---- | ------- |
| **Wide Bezel** | Thick dark border with camera dot | 28 px bezel, rounded corners, drop shadow |
| **Slim Bezel** | Thinner dark border with camera dot | 18 px bezel, rounded corners, drop shadow |
| **Thin Border** | Minimal dark edge | 6 px bezel, no camera dot, subtle shadow |
| **Shadow Only** | No border, floating shadow | No bezel, rounded corners, drop shadow only |
| **No Frame** | Clean, edge-to-edge video | No bezel, no shadow, no padding |

### Output Dimensions

Control the aspect ratio of the exported video:

| Preset | Resolution | Use case |
| ------ | ---------- | -------- |
| **Auto (source)** | Matches recording | Default — no cropping or padding |
| **16:9** | 1920 x 1080 | Standard widescreen, YouTube |
| **3:2** | 1620 x 1080 | Tablets, some laptops |
| **4:3** | 1440 x 1080 | Classic presentation format |
| **1:1** | 1080 x 1080 | Social media (Instagram) |
| **9:16** | 1080 x 1920 | Vertical video (TikTok, Reels, Shorts) |

### Cursor Rendering

The exported video includes a rendered arrow cursor at the recorded mouse position. The cursor is drawn as an SVG arrow shape, properly scaled for the output resolution.

### Keystroke Overlay

Show keyboard shortcuts as floating badges during playback and export. Configure in the **KEYSTROKE OVERLAY** section of the editor panel:

| Setting | Options |
| ------- | ------- |
| **Position** | Bottom-center, Bottom-left, Near cursor |
| **Style** | Floating badge, Minimal text, Key cap |
| **Filter mode** | Shortcuts only (default), Modifiers only, All keystrokes |
| **Display duration** | How long keystroke badges remain visible (default 1500 ms) |
| **Font size** | Badge text size (default 18) |
| **Opacity** | Badge transparency (default 0.85) |

The default filter mode (**shortcuts-only**) shows only combos involving Ctrl/Alt/Win modifiers, preventing accidental exposure of typed passwords.

### Annotations

Add visual annotations to highlight areas of your recording. Three types are available in the **ANNOTATIONS** section:

| Type | Visual | Description |
| ---- | ------ | ----------- |
| **Text** | Text badge with background | White text on dark background at a specific position |
| **Arrow** | Directional line with arrowhead | Yellow arrow pointing from one location to another |
| **Highlight** | Semi-transparent filled rectangle | Colored overlay to draw attention to an area |

All annotations:

- Use **normalized coordinates** (0-1) for resolution independence
- Are **timeline-aware** — visible only during their active time range (default 3 seconds)
- Appear in both the preview and export
- Are saved with the project file

Annotations are rendered behind the cursor and click effects, so interactive elements remain visible on top.

---

## Export

### Recording Pipeline

FollowCursor uses an **H.264 intermediate codec** (CRF 18, ultrafast preset) for buffering recorded frames during capture. This reduces temporary disk usage from ~50 GB/min (lossless) to under 1 GB/min for 4K recordings.

### Export Formats

Click **Export** in the title bar. Two formats are available:

| Format | Extension | Best for |
| ------ | --------- | -------- |
| **MP4 Video** | .mp4 | Sharing, uploading, presentations |
| **GIF Animation** | .gif | GitHub READMEs, Markdown docs, Slack |

**MP4 settings:**

- Codec: H.264 (GPU-accelerated when available, software libx264 fallback)
- Quality: CRF 18 equivalent
- Pixel format: yuv420p
- Voiceover audio: AAC at 192 kbps (if voiceover segments exist)

**GIF settings:**

- Frame rate: 15 fps
- Colors: 256-color palette with Bayer dithering
- Loops forever

### Video Encoder

FollowCursor auto-detects GPU-accelerated H.264 encoders:

| Encoder | GPU Vendor | Notes |
| ------- | ---------- | ----- |
| **NVENC** (h264_nvenc) | NVIDIA | Fastest; requires GeForce/Quadro |
| **QuickSync** (h264_qsv) | Intel | Available on most Intel CPUs |
| **AMF** (h264_amf) | AMD | Available on Radeon GPUs |
| **Software** (libx264) | Any | CPU-based fallback; always available |

Change the encoder via **Settings > Video encoder**. The exporter uses a **two-phase fallback chain** — if the selected encoder fails (at startup or mid-stream), it tries the next GPU encoder before falling back to software.

### What Gets Rendered

Every exported frame includes (composited in order):

1. **Background** — selected gradient, solid, or pattern
2. **Device frame** — bezel, shadow, camera dot
3. **Video content** — recorded frame, zoomed and panned
4. **Annotations** — highlight boxes, arrows, text labels
5. **Cursor** — rendered arrow at the recorded position
6. **Click effects** — animated ripples/bursts/highlights
7. **Keystroke overlay** — keyboard shortcut badges

---

## Trimming

Drag the **yellow trim handles** at both edges of the timeline to cut unwanted content:

- **Left handle** — sets the trim start point
- **Right handle** — sets the trim end point

Trimmed-out regions are hidden from view. Time markers re-index to start at 0:00 from the trim start.

**Constraints:**

- Minimum trimmed region: 500 ms
- Trim handles snap to zoom segment edges
- Right-click a handle and select **Reset trim** to restore the full range
- Trim values are saved with the project

Only the trimmed portion is exported.

---

## Segment Deletion

After splitting a recording into segments, individual segments can be deleted:

- **Right-click** a video segment on the Clips track and select **Delete segment**
- **Left-click** a segment to select it, then press **Delete**

Deleted segments use **ripple delete** — remaining segments close the gap. At least one segment must remain. Zoom keyframes and voiceover segments inside a deleted segment are removed automatically. Segment deletion is **undoable** via Ctrl+Z.

---

## Undo & Redo

All zoom keyframe, click event, video segment, and voiceover changes can be undone and redone, up to **50 snapshots** deep.

| Method | Undo | Redo |
| ------ | ---- | ---- |
| **Keyboard** | Ctrl+Z | Ctrl+Shift+Z or Ctrl+Y |
| **Buttons** | Undo button in editor panel | Redo button in editor panel |

---

## AI Features

FollowCursor includes optional AI-powered features using **Azure AI Foundry** models. These require your own API credentials.

### Setup

1. Open **Settings > AI Settings** in the editor panel
2. Enter your Azure AI Foundry **Endpoint** URL
3. Enter your **API Key** (or GitHub token for GitHub Models)
4. Enter your **Chat Model** deployment name (e.g. gpt-4o-mini)
5. Optionally enter a **TTS Model** deployment name for speech synthesis
6. Choose a **Voice** for TTS
7. Click **OK** — settings are saved automatically

Your API keys are encrypted using **Windows DPAPI** before being stored in the Windows Registry. They are decrypted on-demand and cleared from memory after use.

### AI Smart Zoom

Uses an LLM to analyze your recording activity and generate intelligent zoom keyframes. See the [Zoom System](#ai-smart-zoom) section above for details.

### Voiceover (Text-to-Speech)

Add voiceover segments at specific points in the timeline, write your text, and synthesize speech audio:

**Adding a voiceover segment:**

- In the **VOICEOVER** section, click **Add Voiceover** — adds at the current playback position
- Or **right-click** the timeline and select **Add Voiceover here**

**Working with voiceover segments:**

1. A dialog appears where you enter text and pick a voice
2. Click **Save** to store the segment
3. Click **Synthesize** to generate speech audio via Azure AI Foundry TTS
4. Voiceover segments appear as teal blocks on the timeline Voice track
5. Click a voiceover segment to edit, re-synthesize, or delete it

**During export:**

- All synthesized segments are merged into a single audio track
- Each segment plays at its timeline position
- Audio is encoded as AAC at 192 kbps
- Voiceover is only included in MP4 exports (not GIF)

**Voice options:** Configurable via the AI Settings dialog. The default voice is en-US-Ava:DragonHDLatestNeural. Rate (0.0-3.0) and volume (0.0-3.0) are adjustable per segment.

---

## Chapters

FollowCursor can auto-detect **scene chapters** based on activity patterns:

- Idle gaps of 3+ seconds and major position jumps mark scene boundaries
- Chapter markers appear as flags on the timeline
- Chapters can be embedded as MP4 chapter metadata (for YouTube navigation)
- Manual chapters can also be added

---

## Project Files

### Saving a Project

- **Ctrl+S** saves a .fcproj file
- If previously saved, Ctrl+S re-saves to the same file without prompting
- **Incremental re-save**: only metadata is updated — video data is never re-copied, making re-saves near-instant
- The title bar shows the project name with a dot indicator for unsaved changes
- Export filename defaults to the project name

A .fcproj file is a **ZIP archive** containing:

- project.json — session metadata (mouse positions, key events, click events, zoom keyframes, trim range, settings)
- recording.mp4 — the raw H.264 intermediate video
- voiceover_*.wav — synthesized voiceover audio files (one per segment)

### Loading a Project

Open a .fcproj file to restore the entire session. A loading overlay appears while the ZIP is extracted and the session is restored in the background. All tracked input data, zoom keyframes, annotations, voiceover segments, and visual settings are restored.

### Close Confirmation

When closing with unsaved changes, a confirmation dialog asks: **Save / Don't Save / Cancel**.

---

## Open in Clipchamp

For additional editing, click the **Clipchamp** button to hand off your recording to Microsoft's built-in video editor on Windows 11.

---

## Settings

### Settings Menu

Click the gear icon at the bottom of the editor panel:

| Setting | Description |
| ------- | ----------- |
| **Show zoom debug overlay** | Toggle colored markers on the preview showing detected activity and zoom keyframe positions. Enabled by default. |
| **AI Settings** | Configure Azure AI Foundry credentials for AI zoom and voiceover |
| **Video encoder** | Choose from detected H.264 encoders (GPU or software) |

---

## Keyboard Shortcuts

### Global Hotkeys (work from any application)

| Shortcut | Action |
| -------- | ------ |
| Ctrl+Shift+R | Start or stop recording |
| Ctrl+Shift+= | Zoom in at cursor position (during recording) |
| Ctrl+Shift+- | Zoom out to 1.0x (during recording) |

### Editor Shortcuts

| Shortcut | Action |
| -------- | ------ |
| Space | Play / Pause |
| Z | Insert zoom keyframe at playhead |
| Delete | Remove selected zoom segment, video segment, or click event |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z / Ctrl+Y | Redo |
| Ctrl+S | Save project |

### Mouse Interactions

| Interaction | Where | Action |
| ----------- | ----- | ------ |
| Left-click | Timeline | Seek to that time |
| Left-click | Zoom segment | Select segment |
| Left-click | Click event dot | Select click event |
| Left-click | Video segment | Select video segment |
| Left-click | Voiceover segment | Edit voiceover |
| Right-click | Preview | Add zoom at click position |
| Right-click | Preview (zoomed) | Add pan point |
| Right-click | Timeline (empty) | Add zoom or voiceover |
| Right-click | Zoom segment | Depth / centroid / delete |
| Right-click | Video segment | Delete segment |
| Right-click | Pan point marker | Pick center / reorder / delete |
| Drag edge | Zoom segment | Resize duration |
| Drag body | Zoom segment | Move in time |
| Drag handle | Timeline edge | Set trim start/end |
| Drag marker | Pan point | Change timestamp |

---

## UI Reference

### Title Bar

Custom frameless title bar displaying:

- Application name, project filename (if saved), unsaved-changes indicator
- Version number
- **Export** button (shows progress during export)
- Window controls (minimize, maximize, close)

### Editor Panel

Right sidebar with collapsible sections:

- **ZOOM KEYFRAMES** — list of all keyframes with timestamps, zoom levels, centroids, and reasons
- **Add Zoom** — add a manual zoom keyframe
- **SMART ZOOM** — sensitivity selector + auto-generate and AI buttons
- **VOICEOVER** — add and manage voiceover segments
- **BACKGROUND** — category dropdown + swatch grid (84 presets)
- **DEVICE FRAME** — clickable preset buttons (5 styles)
- **CLICK EFFECTS** — preset picker (8 effects)
- **KEYSTROKE OVERLAY** — toggle and configure keystroke display
- **ANNOTATIONS** — add text, arrows, and highlight boxes
- **CHAPTERS** — auto-detected and manual chapter markers
- **OUTPUT SIZE** — aspect ratio dropdown
- **Undo / Redo** — action buttons
- **Settings** — gear icon for encoder, AI, and debug options
