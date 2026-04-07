# Getting Started

Get up and running in under 5 minutes.

---

## 1. Installation

### Option A: Download a release (recommended)

Download the latest .msix installer or portable .zip from the [GitHub Releases](https://github.com/sabbour/followcursor/releases) page. The MSIX installer is signed and can be double-clicked to install on Windows 10/11.

### Option B: Run from source

**Prerequisites:**

| Requirement | Notes |
| ----------- | ----- |
| **Windows 10 (build 1903+) or Windows 11** | Required for Windows Graphics Capture API |
| **Python 3.13** | [Download](https://www.python.org/downloads/) — check **Add to PATH** during install |
| **ffmpeg** | Bundled automatically via imageio-ffmpeg — no manual install needed |

!!! warning "ARM64 Windows"
    Install the **x64** edition of Python, not ARM64. Many dependencies (OpenCV, windows-capture) don't have ARM64 wheels. x64 Python runs fine via emulation.

**One-command setup:**

```powershell
cd followcursor
.\scripts\Start-Dev.ps1
```

This creates a virtual environment, installs all dependencies, and launches the app.

**Manual setup:**

```powershell
cd followcursor
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### Option C: VS Code

1. Open the repo root in VS Code
2. Press **F5** to launch with the debugger attached
3. Or press **Ctrl+Shift+B** to build a standalone .exe

---

## 2. Record Your First Video

### Step 1 — Pick a source

Click **Select Source** in the sidebar to open the Source Picker.

| Tab | What it captures | Method |
| --- | ---------------- | ------ |
| **Screens** | An entire monitor | Windows Graphics Capture (hardware-accelerated) |
| **Windows** | A single application window | Win32 PrintWindow (no bleed-through) |

Each option shows a live thumbnail so you can confirm the correct source.

### Step 2 — Start recording

Click the red **Start Recording** button. A **3-second countdown** (3, 2, 1) gives you time to switch to the target app. Then:

- The app minimizes to the **system tray**
- A subtle **red border** pulses around the captured area
- **Mouse position** (60 Hz), **keyboard events**, and **clicks** are tracked

!!! tip "Live zoom hotkeys"
    Press **Ctrl+Shift+=** during recording to zoom in at the cursor, or **Ctrl+Shift+-** to zoom back out. These are global hotkeys — they work from any app.

### Step 3 — Stop recording

Press **Ctrl+Shift+R** (global hotkey) or right-click the tray icon and select **Stop Recording**.

The app restores and switches to the **Edit** view with your recording loaded.

---

## 3. Edit & Add Zoom

### Auto-generate zoom keyframes

1. In the **Editor Panel** (right side), find the **SMART ZOOM** section
2. Choose a sensitivity: **Low** (few zooms), **Medium**, or **High** (many zooms)
3. Click **Auto-generate zoom keyframes**

The analyzer detects:

- **Typing bursts** — mouse is still while keys are pressed, zooms into the typing area
- **Click clusters** — clicks in a short window, zooms into the click region (highest priority)

Spatially close activity is merged into sustained zooms, and consecutive clusters are chained — the camera pans between them instead of zooming out and back in.

### Add manual zoom

- **Right-click the preview** to add a zoom at the clicked position
- **Press Z** to insert a keyframe at the playhead position
- **Editor panel** click **Add Zoom** to add at the current playback position

### Edit zoom segments

| Interaction | What it does |
| ----------- | ------------ |
| Right-click a segment | Set depth (Subtle 1.25x, Medium 1.5x, Close 2x, Detail 2.5x), set centroid, or delete |
| Drag a segment edge | Resize the zoom duration |
| Drag the segment body | Move the zoom to a different time |
| Set centroid | Click the preview to reposition where the camera focuses |

### Add pan path points

While viewing a zoom segment, right-click the preview and select **Add pan point here** to create smooth panning within the zoomed view. Pan points show as numbered yellow markers on the timeline.

---

## 4. Customize the Look

| Setting | Options |
| ------- | ------- |
| **Background** | 84 presets in 3 categories — Solid (39), Gradient (37), Pattern (8: wavy) |
| **Device Frame** | Wide Bezel, Slim Bezel, Thin Border, Shadow Only, No Frame |
| **Output Size** | Auto, 16:9, 3:2, 4:3, 1:1, 9:16 |
| **Click Effects** | 8 presets — Subtle Purple, Bold Red, Neon Cyan, and more |
| **Keystroke Overlay** | Show keyboard shortcuts during playback (3 filter modes) |
| **Annotations** | Add text labels, arrows, and highlight boxes |

### Trim the recording

Drag the **yellow trim handles** at the timeline edges to cut unwanted content. Only the trimmed portion is exported. Right-click a handle and select **Reset trim** to undo.

### Undo & Redo

- **Ctrl+Z** to undo, **Ctrl+Shift+Z** or **Ctrl+Y** to redo
- Up to **50 levels** of undo history

---

## 5. Export

Click **Export** in the title bar.

| Format | Extension | Best for |
| ------ | --------- | -------- |
| **MP4 Video** | .mp4 | Sharing, uploading, presentations |
| **GIF Animation** | .gif | GitHub READMEs, Markdown docs, Slack |

- **MP4** — H.264 at CRF 18 quality. GPU-accelerated encoding (NVENC, QuickSync, AMF) is auto-detected with software fallback.
- **GIF** — 15 fps, 256-color palette with Bayer dithering for smooth color transitions.

Export renders every frame with zoom, cursor, click effects, keystroke overlay, annotations, device bezel, and background.

---

## 6. Save & Resume

- **Ctrl+S** — saves a .fcproj file (ZIP bundle with raw video + all metadata + voiceover audio)
- Re-saving is near-instant — only metadata is updated, the video is never re-copied
- The title bar shows the project name and a dot indicator for unsaved changes
- Closing with unsaved changes prompts **Save / Don't Save / Cancel**

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
| Right-click | Preview | Add zoom at click position |
| Right-click | Timeline (empty) | Add zoom or voiceover |
| Right-click | Zoom segment | Depth / centroid / delete |
| Drag edge | Zoom segment | Resize duration |
| Drag body | Zoom segment | Move in time |
| Drag handle | Timeline edge | Set trim start/end |

---

## Troubleshooting

### No monitors found or blank thumbnails

- Make sure you are running on Windows 10 build 1903+ or Windows 11
- Some Remote Desktop sessions don't support WGC — the app falls back to GDI capture automatically

### Recording is laggy

- Close unnecessary apps to free GPU resources
- Check the status bar for WGC confirmation — WGC is hardware-accelerated and should be smooth

### Export takes a long time

- If a GPU encoder is available, it is auto-selected for faster exports
- Check **Settings, Video encoder** to verify which encoder is active
- Progress is shown in the title bar Export button

---

## Next Steps

- Read the **[User Guide](user-guide/recording.md)** for the complete feature reference
- Read the **[Architecture Guide](ARCHITECTURE.md)** to understand the codebase
- Read the **[Contributing Guide](CONTRIBUTING.md)** to start developing
