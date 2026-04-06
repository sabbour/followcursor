"""AI-powered features via Microsoft Foundry (Azure AI).

Provides two AI-enhanced capabilities:

1. **AI Smart Zoom** — Analyzes recording activity (mouse, keyboard, clicks)
   using a large language model to intelligently determine where and when
   to zoom during playback.  Produces the same ``ZoomKeyframe`` objects as
   the local ``activity_analyzer`` but with AI-driven scene understanding.

2. **Text-to-Speech Voiceover** — Synthesizes user-authored voiceover text
   into speech audio via Azure AI Foundry TTS models.  Users add voiceover
   segments at specific timeline positions, enter text, and generate speech.
   Each segment's audio is muxed into the exported video at the correct time.

Users must provide their own Azure AI Foundry API credentials.
"""

import json
import logging
import math
import os
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

from .models import ClickEvent, KeyEvent, MousePosition, ZoomKeyframe, VoiceoverSegment

logger = logging.getLogger(__name__)


# ── Configuration ───────────────────────────────────────────────────


@dataclass
class AISettings:
    """Configuration for Azure AI Foundry API connections.

    A single endpoint and API key are used for chat models and Azure
    Speech Service.  Chat uses the endpoint + deployment name; TTS
    uses the Azure Speech SDK with the same endpoint and key.
    """

    endpoint: str = ""  # Azure AI Foundry / Cognitive Services endpoint URL
    api_key: str = ""  # API key or token
    chat_model: str = ""  # Chat model deployment (e.g. "gpt-4o-mini")
    tts_voice: str = "en-US-Ava:DragonHDLatestNeural"  # Azure Speech voice name

    @property
    def chat_configured(self) -> bool:
        """True when chat completions can be called."""
        return bool(self.endpoint and self.api_key and self.chat_model)

    @property
    def tts_configured(self) -> bool:
        """True when text-to-speech can be called."""
        return bool(self.endpoint and self.api_key)


# ── Prompts ─────────────────────────────────────────────────────────

_ZOOM_SYSTEM_PROMPT = """\
You are a video editing AI that adds cinematic zoom-and-pan effects to screen \
recordings. Your goal is smooth, deliberate camera movements — like a \
professional cameraman gently guiding the viewer's eye to important moments.

You will receive a timestamped activity summary showing mouse position, \
movement speed, keystrokes, and clicks across the recording duration.

**Key principles — smooth and purposeful:**
- FEWER zooms is better. Only zoom on clearly significant activity — \
  sustained typing, deliberate click sequences, or important UI interactions
- Each zoom should feel motivated and unhurried. Prefer longer hold times \
  (3-5 seconds) over quick in-and-out zooms
- When activity stays in the same screen area, use ONE sustained zoom \
  rather than multiple separate zooms
- Leave generous breathing room between zoom sections — at least \
  {min_gap_ms}ms gap. The viewer needs time at full view to orient
- Use moderate zoom levels (1.3-1.6). Deep zooms (>2.0) are disorienting \
  unless the activity is very focused in a small area
- All coordinates are normalized (0.0-1.0) relative to the screen
- Do NOT zoom on idle periods, brief mouse movements, or single isolated clicks
- The recording should feel calm and professional, not frenetic

**Panning while zoomed:**
- When activity moves across the screen DURING a zoom section (e.g. the user \
  clicks several buttons in sequence, or types in one field then moves to \
  another), add pan_points so the camera smoothly follows
- Pan points are intermediate positions the camera visits while staying zoomed
- Only add pan points when the activity genuinely moves — don't pan for \
  small mouse wiggles within the same area
- Each pan point needs a timestamp (ms) when the camera should arrive there

Respond with ONLY a valid JSON array. No markdown, no explanation, no code fences."""

_ZOOM_USER_PROMPT = """\
Analyze this screen recording and generate up to {max_clusters} zoom sections. \
Prefer fewer, longer zooms over many short ones. Use panning when activity \
moves across the screen during a zoom.

{summary}

Return a JSON array where each element has:
- "start_ms": number — when the interesting activity starts (milliseconds)
- "x": number — initial horizontal pan target (0.0 = left, 1.0 = right)
- "y": number — initial vertical pan target (0.0 = top, 1.0 = bottom)
- "zoom": number — zoom level, prefer 1.3-1.6 (max {max_zoom:.1f})
- "hold_ms": number — how long to hold the zoom (3000-5000ms preferred)
- "reason": string — brief description of why this moment is interesting
- "pan_points": array (optional) — if activity moves during the zoom, list \
  intermediate positions: [{{"t_ms": number, "x": number, "y": number}}]
  where t_ms is absolute time in ms. Omit if no panning is needed.

Rules:
- Minimum {min_gap_ms}ms gap between consecutive zoom sections
- Zoom sections MUST NOT overlap — each section must end (start_ms + hold_ms) \
  before the next section's start_ms begins
- Merge nearby activity into one longer zoom rather than multiple short ones
- Use at most {max_clusters} sections total — leave some moments un-zoomed
- pan_points timestamps must be between start_ms and start_ms + hold_ms"""

_NARRATION_SYSTEM_PROMPT = """\
You are a professional narrator for screen recording tutorials. You write \
clear, concise voiceover scripts that describe what the user is doing on \
screen. The narration should feel natural and informative, suitable for \
text-to-speech synthesis.

Write a single flowing narration script that could be read aloud over the \
recording. Keep sentences short and match the pacing of on-screen activity. \
Do not include timestamps or stage directions — just the narration text.

Respond with ONLY the narration text. No markdown formatting."""

_NARRATION_USER_PROMPT = """\
Write a voiceover narration for this screen recording:

{summary}

The narration should:
- Describe the key actions the user performs
- Be concise (aim for roughly 1 sentence per significant action)
- Flow naturally when read aloud
- Total length should be appropriate for a {duration:.0f}-second recording"""


# ── Activity summarizer ─────────────────────────────────────────────


def _summarize_activity(
    mouse_track: List[MousePosition],
    key_events: Optional[List[KeyEvent]],
    click_events: Optional[List[ClickEvent]],
    monitor_rect: dict,
    duration_ms: float,
    window_ms: float = 1000.0,
) -> str:
    """Create a compact text summary of recording activity for the AI prompt.

    Breaks the recording into time windows and summarizes mouse position,
    speed, keystroke count, and click positions for each window.  Empty
    windows are skipped to keep the prompt compact.
    """
    mon_left = monitor_rect.get("left", 0)
    mon_top = monitor_rect.get("top", 0)
    mon_w = max(monitor_rect.get("width", 1), 1)
    mon_h = max(monitor_rect.get("height", 1), 1)

    keys = key_events or []
    clicks = click_events or []
    n_windows = max(1, int(duration_ms / window_ms))

    lines: list[str] = [
        f"Recording duration: {duration_ms / 1000:.1f} seconds",
        f"Screen area: {mon_w}x{mon_h} pixels",
        f"Total: {len(mouse_track)} mouse samples, {len(keys)} keystrokes, {len(clicks)} clicks",
        "",
        "Activity timeline (per-second windows):",
    ]

    for wi in range(n_windows):
        t_start = wi * window_ms
        t_end = t_start + window_ms

        window_mouse = [m for m in mouse_track if t_start <= m.timestamp < t_end]
        n_keys = sum(1 for k in keys if t_start <= k.timestamp < t_end)
        window_clicks = [c for c in clicks if t_start <= c.timestamp < t_end]

        if not window_mouse and n_keys == 0 and not window_clicks:
            continue

        if window_mouse:
            avg_x = sum(m.x for m in window_mouse) / len(window_mouse)
            avg_y = sum(m.y for m in window_mouse) / len(window_mouse)
            nx = max(0.0, min(1.0, (avg_x - mon_left) / mon_w))
            ny = max(0.0, min(1.0, (avg_y - mon_top) / mon_h))

            if len(window_mouse) > 1:
                total_dist = sum(
                    math.sqrt(
                        (window_mouse[i].x - window_mouse[i - 1].x) ** 2
                        + (window_mouse[i].y - window_mouse[i - 1].y) ** 2
                    )
                    for i in range(1, len(window_mouse))
                )
                speed = "fast" if total_dist > 200 else ("medium" if total_dist > 50 else "slow")
            else:
                speed = "still"
        else:
            nx, ny = 0.5, 0.5
            speed = "no data"

        parts = [f"t={wi}s: mouse=({nx:.2f},{ny:.2f}) speed={speed}"]
        if n_keys > 0:
            parts.append(f"keys={n_keys}")
        if window_clicks:
            click_positions = ", ".join(
                f"({max(0.0, min(1.0, (c.x - mon_left) / mon_w)):.2f},"
                f"{max(0.0, min(1.0, (c.y - mon_top) / mon_h)):.2f})"
                for c in window_clicks
            )
            parts.append(f"clicks={len(window_clicks)} at [{click_positions}]")

        lines.append(" | ".join(parts))

    return "\n".join(lines)


# ── Chat API ────────────────────────────────────────────────────────

# Azure OpenAI (Cognitive Services) endpoints contain these hosts.
_AZURE_OPENAI_HOSTS = ("cognitiveservices.azure.com", "openai.azure.com")
_AZURE_OPENAI_API_VERSION = "2024-05-01-preview"


def _build_chat_url(endpoint: str, model: str) -> str:
    """Build the chat completions URL for the given endpoint type.

    Handles three input styles:

    1. **Full deployment URL** — user pasted an Azure OpenAI URL that
       contains ``/openai/deployments/``.  The base URL is extracted
       (everything before ``/openai/deployments/``) and the *model*
       parameter is used as the deployment name — the deployment in
       the pasted URL is ignored so that the Chat Model field controls
       which model is actually called.
    2. **Azure OpenAI base URL** — hostname contains
       ``cognitiveservices.azure.com`` or ``openai.azure.com``.
       Constructs ``{base}/openai/deployments/{model}/chat/completions``.
    3. **Generic inference endpoint** — GitHub Models, Azure AI Foundry.
       Constructs ``{base}/chat/completions``.
    """
    base = endpoint.rstrip("/")

    # Case 1: user pasted a full deployment URL — extract the base
    if "/openai/deployments/" in base:
        base = base[: base.index("/openai/deployments/")]

    # Case 2: Azure OpenAI base URL (original or extracted from Case 1)
    if any(host in base.lower() for host in _AZURE_OPENAI_HOSTS):
        return (
            f"{base}/openai/deployments/{model}"
            f"/chat/completions?api-version={_AZURE_OPENAI_API_VERSION}"
        )

    # Case 3: generic endpoint
    return f"{base}/chat/completions"


def _call_chat(settings: AISettings, system_prompt: str, user_prompt: str) -> str:
    """Call chat completions via REST with retry for transient errors.

    Validates the response structure before accessing nested keys.
    Retries up to 3 times with exponential backoff for 429/500/503.
    """
    import time as _time

    # Validate endpoint uses HTTPS to prevent sending API key over plaintext
    if not settings.endpoint.lower().startswith("https://"):
        raise RuntimeError(
            "AI endpoint must use HTTPS to protect your API key. "
            f"Got: {settings.endpoint[:50]}"
        )

    url = _build_chat_url(settings.endpoint, settings.chat_model)
    logger.info("Chat API URL: %s", url)

    body = json.dumps({
        "model": settings.chat_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }).encode("utf-8")

    req_headers = {
        "Content-Type": "application/json",
        "api-key": settings.api_key,
    }

    _MAX_RETRIES = 3
    _RETRY_CODES = {429, 500, 503}

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        req = urllib.request.Request(
            url, data=body, headers=req_headers, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode(errors="replace")[:500]
            if exc.code in _RETRY_CODES and attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning(
                    "Chat API %s (attempt %d/%d), retrying in %ds: %s",
                    exc.code, attempt + 1, _MAX_RETRIES, wait, error_body[:200],
                )
                _time.sleep(wait)
                last_exc = exc
                continue
            logger.error("Chat API error %s: %s", exc.code, error_body)
            raise RuntimeError(f"Chat API error ({exc.code}): {error_body}") from exc
        except urllib.error.URLError as exc:
            if attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning(
                    "Chat API connection error (attempt %d/%d), retrying in %ds: %s",
                    attempt + 1, _MAX_RETRIES, wait, exc.reason,
                )
                _time.sleep(wait)
                last_exc = exc
                continue
            raise RuntimeError(f"Chat API connection error: {exc.reason}") from exc
        else:
            # Validate response structure
            if not isinstance(data, dict):
                raise RuntimeError("Chat API returned unexpected response format")
            choices = data.get("choices")
            if not choices or not isinstance(choices, list):
                raise RuntimeError("Chat API returned no choices")
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if not message or not isinstance(message, dict):
                raise RuntimeError("Chat API response missing message")
            content = message.get("content", "")
            if not content:
                raise RuntimeError("Chat API returned empty content")
            return content

    raise RuntimeError(f"Chat API failed after {_MAX_RETRIES} retries") from last_exc


# ── Zoom analysis ──────────────────────────────────────────────────


def _parse_zoom_response(
    response_text: str,
    zoom_level: float,
    duration_ms: float,
) -> List[ZoomKeyframe]:
    """Parse AI response JSON into zoom-in / zoom-out keyframe pairs."""
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        sections = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse AI zoom response: %s\nRaw: %s", exc, text[:500])
        raise ValueError(f"AI returned invalid JSON: {exc}") from exc

    if not isinstance(sections, list):
        raise ValueError("AI response is not a JSON array")

    # Cap the number of sections to prevent a malicious/confused LLM
    # from returning thousands of keyframes that cause memory pressure.
    _MAX_AI_SECTIONS = 50
    if len(sections) > _MAX_AI_SECTIONS:
        logger.warning(
            "AI returned %d sections, capping to %d", len(sections), _MAX_AI_SECTIONS
        )
        sections = sections[:_MAX_AI_SECTIONS]

    transition_ms = 600.0
    keyframes: List[ZoomKeyframe] = []

    for section in sections:
        start_ms = float(section.get("start_ms", 0))
        x = max(0.0, min(1.0, float(section.get("x", 0.5))))
        y = max(0.0, min(1.0, float(section.get("y", 0.5))))
        zoom = max(1.1, min(3.0, float(section.get("zoom", zoom_level))))
        hold_ms = float(section.get("hold_ms", 2000))
        reason = str(section.get("reason", "AI-detected activity"))
        pan_points = section.get("pan_points", [])

        # Cap pan points per section to prevent memory exhaustion
        _MAX_PAN_POINTS = 20
        if isinstance(pan_points, list) and len(pan_points) > _MAX_PAN_POINTS:
            logger.warning(
                "Section has %d pan points, capping to %d",
                len(pan_points), _MAX_PAN_POINTS,
            )
            pan_points = pan_points[:_MAX_PAN_POINTS]

        # Clamp viewport to stay within source bounds
        half_vw = 0.5 / zoom
        half_vh = 0.5 / zoom
        x = max(half_vw, min(1.0 - half_vw, x))
        y = max(half_vh, min(1.0 - half_vh, y))

        # Zoom-in keyframe (arrive before the action)
        zoom_in_time = max(0.0, start_ms - transition_ms - 100.0)
        kf_in = ZoomKeyframe.create(
            timestamp=zoom_in_time,
            zoom=zoom,
            x=x,
            y=y,
            duration=transition_ms,
            reason=f"AI: {reason}",
        )
        keyframes.append(kf_in)

        # Pan-point keyframes (same zoom, different position)
        if isinstance(pan_points, list):
            prev_x, prev_y = x, y
            for pp in pan_points:
                if not isinstance(pp, dict):
                    continue
                pp_t = float(pp.get("t_ms", 0))
                pp_x = max(0.0, min(1.0, float(pp.get("x", 0.5))))
                pp_y = max(0.0, min(1.0, float(pp.get("y", 0.5))))
                # Clamp to viewport bounds
                pp_x = max(half_vw, min(1.0 - half_vw, pp_x))
                pp_y = max(half_vh, min(1.0 - half_vh, pp_y))
                # Compute pan duration proportional to distance
                dx = pp_x - prev_x
                dy = pp_y - prev_y
                dist = (dx * dx + dy * dy) ** 0.5
                pan_dur = min(700.0, max(400.0, dist * 1200.0))
                kf_pan = ZoomKeyframe.create(
                    timestamp=max(zoom_in_time + transition_ms, pp_t - pan_dur),
                    zoom=zoom,
                    x=pp_x,
                    y=pp_y,
                    duration=pan_dur,
                    reason=f"AI pan: {reason}",
                )
                keyframes.append(kf_pan)
                prev_x, prev_y = pp_x, pp_y

        # Zoom-out keyframe — ensure the transition completes before
        # the video ends so the zoom-out animation isn't truncated.
        zoom_out_dur = transition_ms * 2
        zoom_out_time = start_ms + hold_ms
        # Clamp so zoom-out start + transition doesn't exceed duration
        max_zoom_out_start = duration_ms - zoom_out_dur
        zoom_out_time = max(0.0, min(zoom_out_time, max_zoom_out_start))
        kf_out = ZoomKeyframe.create(
            timestamp=zoom_out_time,
            zoom=1.0,
            x=0.5,
            y=0.5,
            duration=zoom_out_dur,
            reason=f"AI zoom-out: {reason}",
        )
        keyframes.append(kf_out)

    keyframes.sort(key=lambda k: k.timestamp)

    # ── Prevent overlapping zoom sections ───────────────────────────
    # Find zoom-in/zoom-out pairs and ensure each zoom-out completes
    # before the next zoom-in starts.
    segments: list[tuple[int, int]] = []
    seg_start: int | None = None
    for idx, kf in enumerate(keyframes):
        if kf.zoom > 1.01 and seg_start is None:
            seg_start = idx
        elif kf.zoom <= 1.01 and seg_start is not None:
            segments.append((seg_start, idx))
            seg_start = None

    for s_idx in range(len(segments) - 1):
        _, out_idx = segments[s_idx]
        next_in_idx, _ = segments[s_idx + 1]
        out_kf = keyframes[out_idx]
        in_kf = keyframes[next_in_idx]
        out_end = out_kf.timestamp + out_kf.duration
        if out_end > in_kf.timestamp:
            available = in_kf.timestamp - out_kf.timestamp
            if available > 100:
                keyframes[out_idx] = ZoomKeyframe.create(
                    timestamp=out_kf.timestamp,
                    zoom=out_kf.zoom,
                    x=out_kf.x,
                    y=out_kf.y,
                    duration=max(100, int(available) - 50),
                    reason=out_kf.reason,
                )
            else:
                keyframes[next_in_idx] = ZoomKeyframe.create(
                    timestamp=out_end + 50,
                    zoom=in_kf.zoom,
                    x=in_kf.x,
                    y=in_kf.y,
                    duration=in_kf.duration,
                    reason=in_kf.reason,
                )

    return keyframes


def analyze_activity_with_ai(
    settings: AISettings,
    mouse_track: List[MousePosition],
    monitor_rect: dict,
    duration_ms: float,
    key_events: Optional[List[KeyEvent]] = None,
    click_events: Optional[List[ClickEvent]] = None,
    max_clusters: int = 6,
    zoom_level: float = 1.5,
    min_gap_ms: int = 4000,
) -> List[ZoomKeyframe]:
    """Analyze recording activity with AI to generate zoom keyframes.

    Same return type as ``activity_analyzer.analyze_activity()`` so results
    can be used interchangeably by the zoom engine.
    """
    if not settings.chat_configured:
        raise ValueError(
            "AI chat model is not configured.\n"
            "Set endpoint, API key, and model name in AI Settings."
        )

    summary = _summarize_activity(
        mouse_track, key_events, click_events, monitor_rect, duration_ms,
    )

    user_prompt = _ZOOM_USER_PROMPT.format(
        max_clusters=max_clusters,
        summary=summary,
        max_zoom=min(zoom_level + 0.5, 3.0),
        min_gap_ms=min_gap_ms,
    )

    logger.info("Calling AI for zoom analysis (max_clusters=%d)", max_clusters)
    system_prompt = _ZOOM_SYSTEM_PROMPT.format(min_gap_ms=min_gap_ms)
    response = _call_chat(settings, system_prompt, user_prompt)
    logger.info("AI zoom response length: %d chars", len(response))

    keyframes = _parse_zoom_response(response, zoom_level, duration_ms)
    logger.info("AI generated %d keyframes", len(keyframes))
    return keyframes


# ── Narration ───────────────────────────────────────────────────────


def generate_narration(
    settings: AISettings,
    mouse_track: List[MousePosition],
    monitor_rect: dict,
    duration_ms: float,
    key_events: Optional[List[KeyEvent]] = None,
    click_events: Optional[List[ClickEvent]] = None,
) -> str:
    """Generate narration text for the recording using AI.

    Returns a plain-text narration script suitable for TTS synthesis.
    """
    if not settings.chat_configured:
        raise ValueError("AI chat model is not configured.")

    summary = _summarize_activity(
        mouse_track, key_events, click_events, monitor_rect, duration_ms,
    )

    user_prompt = _NARRATION_USER_PROMPT.format(
        summary=summary,
        duration=duration_ms / 1000.0,
    )

    logger.info("Calling AI for narration generation")
    response = _call_chat(settings, _NARRATION_SYSTEM_PROMPT, user_prompt)
    logger.info("AI narration generated: %d chars", len(response))
    return response.strip()


# ── Text-to-Speech ──────────────────────────────────────────────────


def _extract_region(endpoint: str) -> str:
    """Extract the Azure region from a Cognitive Services endpoint URL.

    ``https://eastus.api.cognitive.microsoft.com`` → ``eastus``
    ``https://myresource.cognitiveservices.azure.com`` → extracts via REST
    Returns empty string if region cannot be determined.
    """
    import re
    # Regional endpoint: https://<region>.api.cognitive.microsoft.com
    m = re.match(r"https?://([^.]+)\.api\.cognitive\.microsoft\.com", endpoint)
    if m:
        return m.group(1)
    # Custom domain: https://<name>.cognitiveservices.azure.com
    # Try to get region from the resource — use a known region mapping
    # For now, try extracting from a HEAD request's headers
    try:
        req = urllib.request.Request(endpoint, method="HEAD")
        with urllib.request.urlopen(req, timeout=5) as resp:
            region = resp.headers.get("x-ms-region", "")
            if region:
                return region.lower()
    except Exception:
        pass
    return ""


def _build_speech_config(api_key: str, endpoint: str):
    """Create a SpeechConfig that works with both regional and custom-domain endpoints."""
    import azure.cognitiveservices.speech as speechsdk

    # Try to use region-based config for better compatibility with HD voices
    region = _extract_region(endpoint)
    if region:
        return speechsdk.SpeechConfig(subscription=api_key, region=region)

    # Fallback to endpoint-based config
    return speechsdk.SpeechConfig(subscription=api_key, endpoint=endpoint)


def synthesize_speech(
    settings: AISettings,
    text: str,
    output_path: str,
    rate: float = 1.0,
    volume: float = 1.0,
) -> str:
    """Convert text to speech via Azure Speech SDK.

    Uses SSML ``<prosody>`` to control speech rate and volume.
    Returns the path to the generated WAV file.
    """
    if not settings.tts_configured:
        raise ValueError(
            "TTS is not configured.\n"
            "Set endpoint and API key in AI Settings."
        )

    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        raise RuntimeError(
            "azure-cognitiveservices-speech package required for TTS.\n"
            "Install with: pip install azure-cognitiveservices-speech"
        )

    endpoint = settings.endpoint.rstrip("/")
    speech_config = _build_speech_config(settings.api_key, endpoint)

    if not output_path.lower().endswith(".wav"):
        output_path = output_path.rsplit(".", 1)[0] + ".wav" if "." in output_path else output_path + ".wav"

    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    speech_config.speech_synthesis_voice_name = settings.tts_voice

    # Use plain text when rate and volume are at defaults
    use_ssml = abs(rate - 1.0) > 0.05 or abs(volume - 1.0) > 0.05

    if use_ssml:
        # Build SSML with prosody
        import html as _html
        # Rate: Azure SSML uses relative percentage (+0% = normal, -50% = half, +100% = double)
        rate_rel = int((rate - 1.0) * 100)
        rate_str = f"{rate_rel:+d}%"
        # Volume: relative percentage (+0% = normal)
        vol_rel = int((volume - 1.0) * 100)
        vol_str = f"{vol_rel:+d}%"
        ssml = (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
            f'<voice name="{_html.escape(settings.tts_voice)}">'
            f'<prosody rate="{rate_str}" volume="{vol_str}">'
            f'{_html.escape(text)}'
            '</prosody></voice></speak>'
        )
        logger.info("TTS SSML: rate=%s volume=%s", rate_str, vol_str)
        result = synthesizer.speak_ssml_async(ssml).get()
    else:
        result = synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        logger.info("TTS audio saved: %s", output_path)
        return output_path
    elif result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        error_msg = f"Speech synthesis canceled: {details.reason}"
        if details.reason == speechsdk.CancellationReason.Error:
            error_msg += f" — {details.error_details}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    else:
        raise RuntimeError(f"Unexpected TTS result: {result.reason}")


# ── Background worker ──────────────────────────────────────────────


class AIWorker(QThread):
    """Background thread for AI operations.

    Runs a single AI task (zoom analysis or TTS) and emits
    the result via the appropriate signal.  Keeps the GUI responsive
    during API calls.
    """

    zoom_result = Signal(list)  # List[ZoomKeyframe]
    tts_result = Signal(str, str)  # (segment_id, audio_file_path)
    error = Signal(str, str)  # (task "zoom"|"tts", error message)
    status = Signal(str)  # progress text

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._task: str = ""
        self._settings: Optional[AISettings] = None
        self._kwargs: dict = {}

    def run_zoom_analysis(self, settings: AISettings, **kwargs) -> None:
        """Start AI zoom analysis in background."""
        self._task = "zoom"
        self._settings = settings
        self._kwargs = kwargs
        self.start()

    def run_tts(self, settings: AISettings, segment_id: str, text: str,
                output_path: str, rate: float = 1.0, volume: float = 1.0) -> None:
        """Start TTS synthesis in background for a specific voiceover segment."""
        self._task = "tts"
        self._settings = settings
        self._kwargs = {
            "segment_id": segment_id, "text": text,
            "output_path": output_path, "rate": rate, "volume": volume,
        }
        self.start()

    def run(self) -> None:  # noqa: D401
        try:
            if self._task == "zoom":
                self.status.emit("Analyzing activity with AI\u2026")
                result = analyze_activity_with_ai(self._settings, **self._kwargs)
                self.zoom_result.emit(result)
            elif self._task == "tts":
                seg_id = self._kwargs.pop("segment_id")
                self.status.emit("Synthesizing speech\u2026")
                result = synthesize_speech(self._settings, **self._kwargs)
                self.tts_result.emit(seg_id, result)
        except Exception as exc:
            logger.exception("AI operation failed: %s", self._task)
            self.error.emit(self._task, str(exc))
