# Project Files

FollowCursor saves your entire session — the raw recording, zoom keyframes, voiceover, annotations, and all settings — into a single `.fcproj` file so you can close and pick up where you left off.

---

## Saving a Project

- Press **Ctrl+S** to save
- The first time you save, you'll be asked to choose a name and location
- After that, **Ctrl+S** saves to the same file instantly — no dialog, no waiting

!!! tip "Re-saves are instant"
    When you save over an existing project, only the metadata is updated — the video is never re-copied. This makes saves near-instant even for long recordings.

The title bar shows the project name. A small dot appears next to it whenever you have unsaved changes, so you always know the current state.

---

## What's Inside a Project File

A `.fcproj` file is a ZIP bundle containing everything needed to restore your session:

| File | Contents |
| ---- | -------- |
| `project.json` | All session data — mouse positions, keystrokes, clicks, zoom keyframes, trim range, annotations, chapter markers, and visual settings |
| `recording.mp4` | Your raw recorded video |
| `voiceover_*.wav` | One audio file per synthesized voiceover segment (if any) |

---

## Opening a Project

Open a `.fcproj` file to fully restore a previous session. A loading overlay appears briefly while everything is unpacked and set up — then your recording, edits, and settings are all exactly as you left them.

---

## Close Confirmation

If you try to close the app with unsaved changes, a dialog will ask you: **Save / Don't Save / Cancel** — so you can never accidentally lose work.
