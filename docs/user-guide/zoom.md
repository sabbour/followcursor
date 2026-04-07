# Zoom & Pan

The zoom system is what makes FollowCursor recordings feel cinematic — it creates smooth camera movements that glide between the areas of your screen your audience needs to see.

---

## How Zoom Works

You add **zoom segments** to your timeline. Each segment tells the camera to zoom in on a specific area for a period of time, then zoom back out. Transitions use a smooth ease-out curve so the camera never snaps or jolts.

---

## Auto-Generate Zoom Keyframes

FollowCursor can analyze your recorded mouse and keyboard activity and automatically suggest where to zoom.

1. In the **Editor Panel** (right sidebar), find the **SMART ZOOM** section
2. Pick a sensitivity level:

| Sensitivity | What it generates |
| ----------- | ----------------- |
| **Low** | Up to 3 zoom areas, with a 6-second gap between them |
| **Medium** | Up to 6 zoom areas, 4-second gap |
| **High** | Up to 10 zoom areas, 2.5-second gap |

3. Click **Auto-generate zoom keyframes**

The analyzer looks for two kinds of activity in your recording:

- **Typing bursts** — when your mouse was still and you were typing, the camera zooms into where you were typing
- **Click clusters** — one or more clicks in a short window; clicks are the strongest signal and always generate a zoom

When related activity happens in the same area, it's merged into a single sustained zoom. When clusters happen close together in different spots, the camera stays zoomed and **pans smoothly** between them rather than zooming out and back in.

!!! tip "Already have zoom keyframes?"
    If you run auto-generate when there are existing zoom segments, you'll be asked whether to replace them or cancel.

---

## AI Smart Zoom

For even smarter results, you can have an AI model analyze your recording and generate zoom suggestions like a professional cameraman would.

See [AI Features](ai.md) for setup instructions. Once configured:

1. In the **SMART ZOOM** section, click **AI Auto-generate zoom**
2. The AI reviews the rhythm and flow of your activity
3. Zoom keyframes are applied automatically — up to 50 sections

---

## Adding Zoom Manually

You have full control to add zoom keyframes anywhere:

- **Right-click the preview** — adds a zoom centered on where you clicked at the current playback position
- **Right-click the timeline** (empty space) — adds a zoom section at that point in time
- **Press Z** — inserts a keyframe at the playhead, centered on where your cursor was during recording
- **Editor Panel → Add Zoom** — adds at the current playback position

---

## Editing Zoom Segments

Zoom segments appear as colored blocks on the timeline. You can adjust them freely:

| Action | How |
| ------ | --- |
| Select a segment | Left-click it |
| Delete a segment | Select it, then press **Delete** |
| Resize the duration | Drag either edge of the segment |
| Move it in time | Drag the segment body left or right |
| Change zoom level or center | Right-click the segment |

### Zoom Depth Levels

Right-click a segment and choose how far in the camera zooms:

| Depth | Zoom Level | Best for |
| ----- | ---------- | -------- |
| **Subtle** | 1.25× | Gentle emphasis — large UI panels or wide areas |
| **Medium** | 1.5× | A good default for most content |
| **Close** | 2.0× | Focused detail — small UI elements, buttons, fields |
| **Detail** | 2.5× | Maximum zoom — fine text, small icons, or code |

### Setting the Camera Focus Point (Centroid)

Each zoom segment has a **centroid** — the point the camera centers on. To change it:

1. Right-click the zoom segment on the timeline
2. Choose **Set centroid**
3. The preview switches to crosshair mode
4. Click the spot on the video where you want the camera to focus

---

## Pan Path Points

When a zoom segment is long, you can guide the camera to different parts of the screen while it stays zoomed in — without ever zooming out.

**To add a pan point:**

1. Make sure the playhead is inside a zoom segment so the preview is zoomed in
2. Right-click on the preview
3. Choose **Add pan point here**

A numbered yellow marker appears on the timeline. Pan points are numbered sequentially so you can see the order the camera will follow.

**Editing pan points:**

| Action | How |
| ------ | --- |
| Move it in time | Drag the marker horizontally |
| Change the camera target | Right-click → **Pick center on preview** |
| Reorder it | Right-click → **Move earlier** or **Move later** |
| Remove it | Right-click → **Delete pan point** |

The camera smoothly interpolates between pan points using ease-in-out transitions.

---

## Zoom Timeline Visual

The timeline shows zoom segments as gradient-colored blocks. Pan point markers appear as numbered yellow circles. This gives you a clear picture of where the camera is active and what path it takes through your recording.
