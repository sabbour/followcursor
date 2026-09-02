# AI Features

FollowCursor includes optional AI-powered features that can analyze your recording, build aligned chapter markers, draft presentation-style voiceover segments, and generate speech — powered by Azure AI Foundry.

---

## Setup

Before using AI features, you need to connect your Azure AI Foundry credentials:

1. Open the Editor Panel and click the **gear icon** at the bottom
2. Choose **AI Settings**
3. Fill in your details:

| Field | What to enter |
| ----- | ------------- |
| **Endpoint** | Your Azure AI Foundry endpoint URL |
| **API Key** | Your API key (or a GitHub token if using GitHub Models) |
| **Chat Model** | The deployment name for AI Smart Zoom (e.g. `gpt-4o-mini`). AI Chapters and automated narration run on **GPT-5.4**. |

4. Click **OK** — your credentials are saved securely

!!! note "Credential security"
    Your API keys are encrypted before being stored and only decrypted when needed to make a request.

---

## AI Smart Zoom

The AI Smart Zoom feature sends a summary of your mouse movements and clicks to a language model. The AI analyzes the flow of your recording — like a professional cameraman reviewing footage — and generates zoom keyframes targeting the most interesting moments.

**To use AI Smart Zoom:**

1. After recording, select **Motion** in the right-side inspector
2. In **SMART ZOOM**, click **Generate with AI**
3. Wait a moment while the AI processes your recording
4. Zoom keyframes are applied automatically (up to 50 sections)

!!! tip "AI vs. local auto-zoom"
    **Generate locally** is faster and works offline. AI Smart Zoom is better at understanding narrative pacing — for example, giving weight to visually important moments rather than just activity frequency.

---

## AI Chapters

Generate chapter markers from the same shared recording understanding that powers narration. FollowCursor reuses frame samples plus mouse movement, clicks, and zoom edits so the chapter flags line up with the real beats of the walkthrough instead of only with idle gaps.

**To generate chapters:**

1. After recording, select **Audio** and open **CHAPTERS**
2. Click **Generate chapters**
3. Wait while FollowCursor samples the recording and drafts the chapter markers
4. Review the flag markers on the timeline. Hover a flag to see its name, left-click to jump there, or right-click to jump/delete it
5. Re-running replaces only the previous generated chapter markers. Any manual chapter markers stay where you put them

Generated and manual chapter markers are written into MP4 chapter metadata during export.

---

## Automated narration

Generate five presentation-style voiceover segments for the whole recording. FollowCursor builds the narration context from the same shared recording understanding used by AI Chapters — steady frame samples plus mouse movement, clicks, and existing zoom edits — then asks **GPT-5.4** for a structured script with these sections in order:

- **Context**
- **Background**
- **Prompt / Action**
- **Walkthrough**
- **Result**

For longer recordings, FollowCursor analyzes the visuals in provider-safe batches and then synthesizes one final script, so narration quality stays high without overrunning image limits. The app saves that combined script as `<video_name>_voiceover.md` beside the current recording, creates generated voiceover segments at the returned timestamps, and starts speech automatically through the normal voiceover flow with your current default TTS voice from **AI Settings**. The timeline keeps short section labels, while the editor opens the clean spoken line instead of the markdown heading text. If the first draft is too short or too long for the recording, FollowCursor does one timing-aware rewrite and can apply a subtle TTS rate nudge per segment so the combined narration stays close to the video length without obvious silence padding. The prompt is tuned to sound like a peer presentation or pitch, not a screen-reader recap. Clicks and zoom cues still shape emphasis behind the scenes, but the spoken copy stays on the action, intent, and payoff rather than narrating on-screen mechanics directly. The same shared recording analysis also feeds AI chapter generation, so narration and chapter beats stay aligned instead of drifting apart.

**To generate narration:**

1. After recording, select **Audio** and open **VOICEOVER**
2. Click **Generate**
3. Wait while FollowCursor writes the script, adds the generated voiceover segments, and starts speech automatically through the normal voiceover flow
4. Review the generated segments on the timeline's **Voice** track. Each block keeps a short section label, while the editor shows the spoken line if you double-click or right-click to edit it, drag it to retime it, or delete it with confirmation
5. Save the project if you want the narration to travel with the `.fcproj` file

If you generate narration again, FollowCursor replaces the previous generated voiceover segments but keeps any manual voiceover segments. If you later ripple-delete a clip segment, FollowCursor keeps generated narration when it can by trimming, retiming, rewriting the saved markdown, and re-synthesizing the affected generated voiceover segments. Manual voiceovers that overlap the deleted clip are still removed because their audio cannot be rewritten safely.

---

## AI chapter markers

Generate chapter markers from the same shared recording knowledge used by narration. FollowCursor reuses the frame samples, activity summary, click beats, zoom edits, and any provider-safe batch notes so the chapter titles land on the same major beats as the narration draft without paying for a second disconnected analysis pass.

**To generate AI chapters:**

1. Select **Audio** and open **CHAPTERS**
2. Click **Generate chapters**
3. Wait while FollowCursor analyzes the shared recording context and replaces the previously generated chapter markers
4. Review the chapter flags on the timeline. Any manual chapter markers you added stay in place

Chapter titles are short timeline-friendly labels meant for navigation and MP4 metadata. They summarize major workflow shifts; they do not read out every click, zoom, or cursor movement literally.

---

## Manual voiceover segments

Add spoken narration at specific points on the timeline. You write the text and FollowCursor synthesizes it into speech using Azure AI Foundry TTS.

### Adding a Voiceover Segment

You can add a voiceover segment in two ways:

- Select **Audio**, open **VOICEOVER**, and click **Add here** — this places a segment at the current playback position
- Right-click the timeline and choose **Add Voiceover here**

### Working with a Voiceover Segment

1. A dialog opens — type the text you want spoken
2. Pick a voice from the available options
3. Adjust **Rate** (speed, 0.0–3.0) and **Volume** (0.0–3.0) if needed
4. Click **Preview** if you want to hear the current draft first
5. Click **OK** to store the segment and synthesize its speech audio

Synthesized voiceover segments appear as **teal blocks** on the timeline's Voice track. Double-click or right-click any block to edit the text, change the voice, re-synthesize, or delete it. Generated narration segments use the same track, so deleting one also updates the saved `<video_name>_voiceover.md` script sidecar.

### Voice Options

Available voices are loaded dynamically from your configured text-to-speech service. When creating or editing a voiceover segment, choose from the voices currently listed in the voice selector for that segment.

| Attribute | Range | Default |
| --------- | ----- | ------- |
| **Rate** | 0.0–3.0 | 1.0 (normal speed) |
| **Volume** | 0.0–3.0 | 1.0 (normal volume) |

### Voiceover in the export

- Generated voiceover segments from narration and any manual voiceover segments are merged into a single audio track at their timeline positions
- Voiceover is only included in **MP4 exports** — GIF files do not carry audio
