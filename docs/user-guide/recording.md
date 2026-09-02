# Screen & Window Recording

FollowCursor captures your screen or any individual window, then tracks your mouse and clicks so you can add zoom effects in the editor.

!!! note "Startup splash"
    FollowCursor shows a brief splash screen while the recorder, tray controls, and editor shell initialise. It closes automatically as soon as the main window is ready.

---

## Choosing a Source

Click **Choose recording source** in the preview to open the Source Picker. Two tabs let you choose what to capture:

| Tab | What it captures |
| --- | ---------------- |
| **Screens** | An entire monitor — useful for full-screen demos and walkthroughs |
| **Windows** | A single application window — the recording stays isolated to that app, even if other windows overlap it |

Each option shows a live thumbnail preview so you can confirm the right source before you start. Selecting a source starts its preview only. FollowCursor does not record until you press **Record**.

Use **Tab** to move keyboard focus through the source cards. Press **Enter** or **Space** to select the focused source, then choose **Select**.

!!! tip "Multiple monitors"
    If you have more than one monitor, each one appears separately under the **Screens** tab. Pick the one you want.

---

## Starting a Recording

1. Select your source in the Source Picker
2. Click the red **Record** button

A **3-second countdown** (3, 2, 1) appears on the preview — this gives you time to switch to the app you're recording before the camera starts rolling.

Once the countdown finishes:

- The app minimizes to the **system tray**
- A subtle **red border** pulses around the captured monitor so you know recording is active
- Your mouse position and clicks are tracked automatically

You can also start (and stop) recording from any app using the global hotkey **Ctrl+Shift+R**.

---

## Live Zoom During Recording

You don't have to wait until the edit stage to add zoom — you can zoom in and out in real time while you're recording:

| Hotkey | Action |
| ------ | ------ |
| **Ctrl+Shift+=** | Zoom in at your current cursor position |
| **Ctrl+Shift+-** | Zoom back out to full view |

These hotkeys work from any application while FollowCursor is recording in the background.

---

## Stopping a Recording

Stop at any time using either method:

- Press **Ctrl+Shift+R** (global hotkey — works from any app)
- Right-click the **system tray icon** and choose **Stop Recording**

The app comes back up and switches straight to the editor with your recording loaded and ready to work on.

!!! note "Processing moment"
    A brief processing overlay appears while the recording is being finalised. It disappears automatically when your video is ready to edit.

## Adding Captures to a Project

To continue recording in the same project, click **Add Capture** below the preview. You can also select **Add** in the sidebar. FollowCursor opens the source picker each time, so you can choose any screen or window for the new section. Record the section and stop as usual.

FollowCursor adds the capture to the end of the current timeline. Existing zooms, voiceovers, chapters, and edits stay in place. You can repeat this workflow to build one project from multiple recording sessions.

Additional sources are fitted to the first capture's canvas without stretching. FollowCursor adds padding when the aspect ratios differ and remaps cursor and click positions to the fitted image.
