# FollowCursor — Quickstart Guide

Get up and running in under 5 minutes.

---

## 1. Prerequisites

| Requirement | Notes |
| ----------- | ----- |
| **Windows 10 (build 1903+) or Windows 11** | Required for Windows Graphics Capture API |
| **Python 3.10 or newer** | [Download](https://www.python.org/downloads/) — check **"Add to PATH"** during install |
| **ffmpeg** | Bundled automatically via `imageio-ffmpeg` — no manual install needed |

## 2. Install & Launch

### Option A: One-command setup (recommended)

Open a terminal in the `followcursor/` folder and run:

```bat
dev.bat
```

This will:

1. Create a Python virtual environment (`.venv/`)
2. Install all dependencies from `requirements.txt`
3. Launch the app

### Option B: Manual setup

```bat
cd followcursor
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Option C: VS Code

1. Open the repo root in VS Code
2. Press **F5** to launch with the debugger attached
3. Or press **Ctrl+Shift+B** to build a standalone `.exe`

---

## 3. Record Your First Video

### Step 1 — Pick a source

Click the **⏺ Record** button in the sidebar, then click **Select Source**.

- **Screens tab** — pick a monitor to capture the full display
- **Windows tab** — pick a specific window (captured without bleed-through from other windows)

### Step 2 — Start recording

Click the red **⏺ Start Recording** button. A 3-second countdown appears, then:

- The app minimizes to the system tray
- A subtle red border pulses around the captured area
- Mouse position (60 Hz), keyboard events, and clicks are tracked

> **Tip:** Press **Ctrl+Shift+=** during recording to zoom in at the cursor, or **Ctrl+Shift+-** to zoom back out. These are global hotkeys that work from any app.

### Step 3 — Stop recording

Press **Ctrl+Shift+R** or right-click the tray icon → **Stop Recording**.

The app restores from the tray and switches to the **Edit** view.

---

## 4. Edit & Add Zoom

### Auto-generate zoom keyframes

1. In the **Editor Panel** (right side), find the **SMART ZOOM** section
2. Choose a sensitivity: **Low** (few zooms), **Medium**, or **High** (many zooms)
3. Click **✨ Auto-generate zoom keyframes**

The analyzer detects three types of activity:

- **Mouse settlements** — cursor moves fast then stops
- **Typing bursts** — mouse is still while keys are pressed (nearby bursts in the same area are merged)
- **Click clusters** — multiple clicks in a short window (spatially close clusters stay zoomed in)

### Add manual zoom

- **Right-click the preview** → **🔍 Add Zoom here** — places a zoom keyframe at the clicked position
- **Editor panel** → **🔍 Add Zoom** — adds a keyframe at the current playback position

### Edit zoom segments

- **Right-click a zoom segment** on the timeline to:
  - Set depth: Subtle (1.25×), Medium (1.5×), Close (2×), Detail (2.5×)
  - **📍 Set centroid** — click the preview to reposition the zoom center
  - **🗑 Delete zoom section**
- **Drag segment edges** to resize the zoom duration
- **Drag the segment body** to move the entire zoom in time

### Customize the look

| Setting | Options |
| ------- | ------- |
| **Background** | 84 presets in 3 categories — Solid (39) · Gradient (37) · Pattern (8: wavy) |
| **Device Frame** | Wide Bezel · Slim Bezel · Thin Border · Shadow Only · No Frame |
| **Output Size** | Auto · 16:9 · 3:2 · 4:3 · 1:1 · 9:16 |

### Trim the recording

Drag the **yellow trim handles** at the edges of the timeline to cut unwanted content from the start or end. The trimmed region is dimmed, and only the trimmed portion is exported.

### Undo & Redo

- **Ctrl+Z** to undo the last zoom keyframe change
- **Ctrl+Shift+Z** or **Ctrl+Y** to redo
- Or use the **↩ Undo** / **Redo ↪** buttons at the bottom of the editor panel

---

## 5. Export

Click **⬆ Export** in the title bar.

- Choose a destination folder and filename
- Export renders every frame with zoom, cursor overlay, click ripple effects, device bezel, and background
- Output: H.264 MP4 at CRF 18 equivalent quality (GPU-accelerated encoding when available, software fallback)

---

## 6. Save & Resume Later

- **Ctrl+S** or **File → Save Project** — saves a `.fcproj` file (ZIP bundle containing the raw video + all metadata). Re-saves to the same file if previously saved.
- **File → Open Project** — load a `.fcproj` to continue editing
- The title bar shows the current project name and a **●** indicator when there are unsaved changes
- Closing the app with unsaved changes prompts a **Save / Don’t Save / Cancel** confirmation

---

## Keyboard Shortcuts

| Shortcut | Action |
| -------- | ------ |
| `Ctrl+Shift+R` | Start/stop recording (global — works from any app) |
| `Ctrl+Shift+=` | Zoom in at cursor position (during recording) |
| `Ctrl+Shift+-` | Zoom out to 1.0× (during recording) |
| Right-click zoom segment | Edit depth / centroid / delete |
| Right-click preview | Add zoom at click position |
| Drag segment edge | Resize zoom duration |
| Drag segment body | Move zoom in time |
| Click event dot | Select click event |
| `Delete` | Remove selected click event |
| `Ctrl+Z` | Undo last zoom keyframe change |
| `Ctrl+Shift+Z` / `Ctrl+Y` | Redo last undone change |
| `Space` | Play / Pause |
| `Z` | Insert zoom keyframe at playhead |
| `⏮` / `⏭` | Skip to start / end |

---

## Troubleshooting

### "No monitors found" or blank thumbnails

- Make sure you're running on Windows 10 build 1903+ or Windows 11
- Some Remote Desktop sessions don't support Windows Graphics Capture — if WGC fails, the app falls back to GDI capture automatically

### Recording is laggy or dropped frames

- Close unnecessary apps to free GPU resources
- WGC (Windows Graphics Capture) is hardware-accelerated and should be smooth on most systems; check the status bar for "⚡ WGC" confirmation

### Export takes a long time

- Export renders every frame with zoom/cursor/bezel — this can be intensive
- If a GPU encoder is available (NVENC, QuickSync, AMF), it's auto-selected for faster exports. Check **⚙ Settings → Video encoder** to verify
- Progress is shown in the title bar's Export button

### Red recording border not visible

- The border draws inside the monitor bounds. On multi-monitor setups, it should be visible on the captured monitor. If you're recording a window (not a full monitor), no border is shown.

---

## Next Steps

- Read the [Architecture Guide](ARCHITECTURE.md) to understand how the codebase is structured
- Read the [Contributing Guide](CONTRIBUTING.md) to set up a development environment
