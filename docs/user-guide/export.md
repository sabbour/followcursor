# Export

When you're happy with your recording and edits, export it as a polished video file ready to share.

---

## Export Formats

Click **Export** in the title bar to choose a format:

| Format | Extension | Best for |
| ------ | --------- | -------- |
| **MP4 Video** | .mp4 | Sharing, uploading to YouTube, Loom, presentations |
| **GIF Animation** | .gif | GitHub READMEs, Markdown docs, Slack, Discord |

- **MP4** — high quality video with smooth motion. GPU-accelerated encoding is used automatically if available, with a software fallback.
- **GIF** — 15 fps, 256-color output. Loops forever. No audio.

!!! tip "Which format should I use?"
    MP4 is almost always the better choice — it's smaller, higher quality, and supports voiceover audio. Use GIF when the destination (a GitHub README, for example) doesn't support video embeds.

---

## Trimming

Before you export, you can trim the start and end of the recording to remove any parts you don't need.

Drag the **yellow trim handles** at both edges of the timeline:

- **Left handle** — sets where the export starts
- **Right handle** — sets where the export ends

Only the region between the handles is exported. Right-click a handle and choose **Reset trim** to restore the full length.

---

## Segment Deletion

If you've split your recording into segments, you can delete individual ones before exporting:

- **Right-click** a video segment on the Clips track and choose **Delete segment**
- Or left-click to select it, then press **Delete**

Deleted segments use **ripple delete** — the remaining clips close the gap automatically. Zoom keyframes and voiceover segments that were inside the deleted portion are removed too. You can always undo with **Ctrl+Z**.

---

## Chapter Markers

Chapters appear as flag markers on your timeline and can be embedded as navigation points in the exported MP4 — useful for longer recordings or tutorials where viewers might want to skip to a section.

FollowCursor detects chapters automatically:

- Gaps in activity (3+ seconds of idle time)
- Major cursor position jumps

You can also add chapters manually. Chapters are included in the MP4 file metadata and supported by players like YouTube and VLC.

!!! note "Chapters in GIF exports"
    Chapter markers are not embedded in GIF files — they are an MP4-only feature.

---

## What Gets Rendered

Every frame of the export includes all of your edits, composited in this order:

1. **Background** — your chosen gradient, solid color, or pattern
2. **Device frame** — bezel, shadow, or no frame
3. **Video content** — your recorded screen, zoomed and panned
4. **Annotations** — text labels, arrows, and highlight boxes
5. **Cursor** — your mouse cursor at the recorded position
6. **Click effects** — animated ripples or highlights at click locations
7. **Keystroke overlay** — keyboard shortcut badges

What you see in the preview is exactly what will be in the exported file.

---

## Export Progress

A progress indicator appears in the **Export** button in the title bar while your video is rendering. For longer recordings, GPU-accelerated encoding significantly speeds this up.
