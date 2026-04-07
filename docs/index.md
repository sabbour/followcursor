# FollowCursor

**A Windows screen recorder with cinematic cursor-following zoom.**

Record your screen or any individual window, then export a polished MP4 video where the camera smoothly follows and zooms into your cursor movements. Perfect for tutorials, demos, and product walkthroughs.

![FollowCursor screenshot](screenshot.png)

---

## Key Features

- **Screen & Window Recording** — Capture any monitor (hardware-accelerated) or individual windows
- **Smart Auto-Zoom** — Automatically detects typing bursts and click clusters to generate zoom keyframes
- **AI Smart Zoom** — Use Azure AI Foundry chat models to generate intelligent zoom-and-pan keyframes like a professional cameraman
- **AI Voiceover (TTS)** — Add text-to-speech voiceover segments with multiple voice options
- **Manual Zoom Keyframes** — Right-click the timeline or preview to add zoom points; drag segments to reposition
- **Pan Path Points** — Add intermediate pan waypoints within a zoomed segment for smooth panning
- **Cinematic Export** — H.264 MP4 via ffmpeg with ease-out easing, cursor rendering, click ripple effects, and device frame overlays
- **Background Presets** — 84 backgrounds (solids, gradients, patterns) with category picker
- **Device Frames** — 5 frame styles from wide bezel to frameless
- **Project Files** — Save/load `.fcproj` bundles to resume editing later
- **Undo & Redo** — Full undo/redo for all zoom keyframe and click event changes
- **Frameless Dark UI** — Custom title bar, dark theme with purple accents

## Architecture

| Layer | Technology | Purpose |
| ----- | ---------- | ------- |
| UI Framework | PySide6 (Qt 6) | Widgets, layout, painting, signals/slots |
| Screen Capture | Windows Graphics Capture | Hardware-accelerated monitor/window capture |
| Video Export | ffmpeg (libx264 / HW accel) | H.264 MP4 encoding with zoom/cursor baked in |
| Image Processing | OpenCV + NumPy | Frame manipulation, thumbnails, cursor rendering |
| Input Tracking | Win32 Hooks (ctypes) | Low-level mouse, keyboard, and click tracking |
| Zoom Engine | Pure Python | Ease-out-eased keyframe interpolation |
| AI Features | azure-ai-inference | AI zoom analysis, TTS voiceover via Azure AI Foundry |

## Getting Started

Check out the [Quickstart Guide](QUICKSTART.md) to get recording in under 5 minutes.

## Contributing

See the [Contributing Guide](CONTRIBUTING.md) for development setup, coding conventions, and how to submit changes.
