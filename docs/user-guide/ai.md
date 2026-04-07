# AI Features

FollowCursor includes optional AI-powered features that can automatically analyze your recording and generate a voiceover — powered by Azure AI Foundry.

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
| **Chat Model** | The deployment name for your language model (e.g. `gpt-4o-mini`) |

4. Click **OK** — your credentials are saved securely

!!! note "Credential security"
    Your API keys are encrypted before being stored and only decrypted when needed to make a request.

---

## AI Smart Zoom

The AI Smart Zoom feature sends a summary of your mouse movements, keystrokes, and clicks to a language model. The AI analyzes the flow of your recording — like a professional cameraman reviewing footage — and generates zoom keyframes targeting the most interesting moments.

**To use AI Smart Zoom:**

1. After recording, open the Editor Panel
2. In the **SMART ZOOM** section, click **AI Auto-generate zoom**
3. Wait a moment while the AI processes your recording
4. Zoom keyframes are applied automatically (up to 50 sections)

!!! tip "AI vs. local auto-zoom"
    The local **Auto-generate zoom keyframes** button is faster and works offline. AI Smart Zoom is better at understanding narrative pacing — for example, giving weight to visually important moments rather than just activity frequency.

---

## Voiceover (Text-to-Speech)

Add spoken narration to your recording at any point on the timeline. You write the text and FollowCursor synthesizes it into speech using Azure AI Foundry TTS.

### Adding a Voiceover Segment

You can add a voiceover segment in two ways:

- In the **VOICEOVER** section of the Editor Panel, click **Add Voiceover** — this places a segment at the current playback position
- Right-click the timeline and choose **Add Voiceover here**

### Working with a Voiceover Segment

1. A dialog opens — type the text you want spoken
2. Pick a voice from the available options
3. Adjust **Rate** (speed, 0.0–3.0) and **Volume** (0.0–3.0) if needed
4. Click **Save** to store the segment
5. Click **Synthesize** to generate the speech audio

Synthesized voiceover segments appear as **teal blocks** on the timeline's Voice track. Click any block to edit the text, change the voice, re-synthesize, or delete it.

### Voice Options

Available voices are loaded dynamically from your configured text-to-speech service. When creating or editing a voiceover segment, choose from the voices currently listed in the voice selector for that segment.

| Attribute | Range | Default |
| --------- | ----- | ------- |
| **Rate** | 0.0–3.0 | 1.0 (normal speed) |
| **Volume** | 0.0–3.0 | 1.0 (normal volume) |

### Voiceover in the Export

- All synthesized segments are merged into a single audio track at their timeline positions
- Voiceover is only included in **MP4 exports** — GIF files do not carry audio
