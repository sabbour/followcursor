"""Analyze mouse + keyboard + click activity to auto-generate zoom keyframes.

Detects three kinds of interesting moments:

1. **Mouse settlements** — cursor moves fast then *stops*.  The zoom targets
   the settlement position (where the user lands), not the burst itself,
   because fast movement is transition and the destination is the content.
   Score = deceleration magnitude (speed drop between consecutive windows).

2. **Typing zones** — mouse nearly stationary while keys are being pressed.
   The cursor position tells us *where* the user is typing.
   Score = keystrokes-per-second in the window (only when mouse is slow).

3. **Click clusters** — ≥2 mouse clicks within a 3-second sliding window.
   Zoom targets the centroid of the clicks in that burst.

All signal types are merged into a single scored timeline, clustered,
and the top clusters get zoom-in / zoom-out keyframe pairs.

Signal weighting: typing > clicks > mouse settlements, so zoom prefers
moments where the user is actively working over raw cursor movement.
"""

import logging
import math
from typing import List, Optional, Tuple

from .models import MousePosition, KeyEvent, ClickEvent, ZoomKeyframe

logger = logging.getLogger(__name__)


# ── Tuning constants ────────────────────────────────────────────────

WINDOW_MS = 500           # time window for averaging (ms)
MIN_GAP_MS = 4000         # minimum gap between separate clusters (was 2500)
PEAK_TOP_N = 6            # max activity clusters
ZOOM_LEVEL = 1.5          # zoom factor for auto-keyframes (overridden by depth setting)
ZOOM_HOLD_MOUSE_MS = 2000 # hold for mouse settlements (was 1500)
ZOOM_HOLD_TYPING_MS = 3000 # hold longer for typing (user is still working)
ZOOM_HOLD_CLICK_MS = 2000  # hold for click clusters
TRANSITION_MS = 600       # easing duration (zoom-in)
PAN_TRANSITION_MS = 400   # base duration for panning to new target while zoomed
PAN_TRANSITION_MAX_MS = 700  # cap pan duration even for large distances
PAN_MERGE_GAP_MS = 3000  # if next cluster starts within this gap of current cluster ending, pan instead of zoom-out/in
MAX_CHAIN_LENGTH = 4     # max clusters in a single pan chain before forcing a zoom-out
ANTICIPATION_MS = 100     # arrive this many ms *before* action starts so the viewer sees the trigger

# Thresholds
TYPING_MIN_KPS = 1.0      # minimum keys-per-second to count as typing
MOUSE_STILL_PX_MS = 0.5   # mouse speed below this = "still" (px/ms)
MOUSE_TYPING_PX_MS = 3.0  # mouse speed below this = "slow enough for typing" (px/ms)
DECEL_MIN_RATIO = 3.0     # speed must drop by at least this factor to count
CLICK_WINDOW_MS = 3000    # sliding window for click-cluster detection
CLICK_MIN_COUNT = 1       # minimum clicks in window to trigger zoom

# Signal weights (higher = preferred when ranking mixed clusters)
WEIGHT_TYPING = 1.0
WEIGHT_CLICK = 0.8
WEIGHT_MOUSE = 0.5

# Spatial-aware clustering: merge same-type peaks that are close in space
CLICK_MERGE_GAP_MS = 8000    # merge click peaks within 8s if spatially close
TYPING_MERGE_GAP_MS = 6000   # merge typing peaks within 6s if spatially close
SPATIAL_MERGE_DIST = 0.15    # normalized distance threshold for spatial proximity

# Pan dampening: don't drag viewport center all the way to the target
PAN_VIEWPORT_MARGIN = 0.15   # margin fraction within viewport edge


def _dampen_pan(
    target_x: float, target_y: float, zoom: float,
    margin: float = PAN_VIEWPORT_MARGIN,
    from_x: float = 0.5, from_y: float = 0.5,
) -> Tuple[float, float]:
    """Compute pan to keep *target* visible within the zoomed viewport.

    Starts from (*from_x*, *from_y*) — the viewport center before this
    move — and shifts the minimum amount needed so the target lands
    inside the visible area with a small margin from the edge.

    At low zoom levels most positions are already visible and no
    panning is needed at all.
    """
    if zoom <= 1.0:
        return 0.5, 0.5

    # Half of viewport extent in normalised coords
    half_vw = 0.5 / zoom
    half_vh = 0.5 / zoom

    # Shrink by margin so the target isn't right at the edge
    eff_hw = half_vw * (1.0 - margin)
    eff_hh = half_vh * (1.0 - margin)

    pan_x, pan_y = from_x, from_y

    # Shift only if the target falls outside the effective visible band
    if target_x < pan_x - eff_hw:
        pan_x = target_x + eff_hw
    elif target_x > pan_x + eff_hw:
        pan_x = target_x - eff_hw

    if target_y < pan_y - eff_hh:
        pan_y = target_y + eff_hh
    elif target_y > pan_y + eff_hh:
        pan_y = target_y - eff_hh

    # Clamp so the viewport doesn't fly off the edge of the source
    pan_x = max(half_vw, min(1.0 - half_vw, pan_x))
    pan_y = max(half_vh, min(1.0 - half_vh, pan_y))

    return pan_x, pan_y


def analyze_activity(
    mouse_track: List[MousePosition],
    monitor_rect: dict,
    key_events: Optional[List[KeyEvent]] = None,
    click_events: Optional[List[ClickEvent]] = None,
    max_clusters: int = PEAK_TOP_N,
    zoom_level: float = ZOOM_LEVEL,
    follow_cursor: bool = True,
    min_gap_ms: int = MIN_GAP_MS,
) -> List[ZoomKeyframe]:
    """Detect activity clusters from mouse + keyboard + click data.

    Args:
        zoom_level: Zoom factor for auto-keyframes (e.g. 1.25, 1.5, 2.0).
        follow_cursor: If True, pan follows cursor; if False, zoom to center.
        max_clusters: Maximum number of activity clusters to generate.
        min_gap_ms: Minimum gap between separate clusters (ms).

    Returns zoom-in / zoom-out keyframe pairs sorted by timestamp.
    """
    if len(mouse_track) < 10:
        return []

    mon_left = monitor_rect.get("left", 0)
    mon_top = monitor_rect.get("top", 0)
    mon_w = max(monitor_rect.get("width", 1), 1)
    mon_h = max(monitor_rect.get("height", 1), 1)

    key_timestamps = [k.timestamp for k in key_events] if key_events else []
    click_list = click_events or []

    logger.info(
        "Analyzing: %d mouse samples, %d key events, %d click events, duration=%.0fms",
        len(mouse_track), len(key_timestamps), len(click_list),
        mouse_track[-1].timestamp,
    )

    # ── 1. Per-sample mouse velocity + normalized position ──────────
    samples: List[Tuple[float, float, float, float]] = []
    for i in range(1, len(mouse_track)):
        prev, curr = mouse_track[i - 1], mouse_track[i]
        dt = max(curr.timestamp - prev.timestamp, 1.0)
        dx = curr.x - prev.x
        dy = curr.y - prev.y
        speed = math.sqrt(dx * dx + dy * dy) / dt
        nx = max(0.0, min(1.0, (curr.x - mon_left) / mon_w))
        ny = max(0.0, min(1.0, (curr.y - mon_top) / mon_h))
        samples.append((curr.timestamp, speed, nx, ny))

    if not samples:
        return []

    duration = samples[-1][0]
    n_windows = max(1, int(duration / WINDOW_MS))

    # ── 2. Score each window ────────────────────────────────────────
    # Each window gets:
    #   mouse_score  = deceleration (speed drop from previous window)
    #   typing_score = keys-per-second (only when mouse is slow)
    #   label        = "mouse" | "typing"

    WindowInfo = Tuple[float, float, float, float, str]  # (time, score, x, y, label)
    windows: List[WindowInfo] = []

    # First pass: compute average speed per window
    window_speeds: List[Tuple[float, float, float, float]] = []  # (center_t, avg_speed, avg_x, avg_y)
    for wi in range(n_windows):
        t_start = wi * WINDOW_MS
        t_end = t_start + WINDOW_MS

        bucket = [s for s in samples if t_start <= s[0] < t_end]
        if not bucket:
            window_speeds.append(((t_start + t_end) / 2, 0.0, 0.5, 0.5))
            continue

        avg_speed = sum(b[1] for b in bucket) / len(bucket)
        avg_x = sum(b[2] for b in bucket) / len(bucket)
        avg_y = sum(b[3] for b in bucket) / len(bucket)
        center_t = (t_start + t_end) / 2
        window_speeds.append((center_t, avg_speed, avg_x, avg_y))

    # Second pass: detect settlements (big deceleration) and typing zones
    for wi in range(n_windows):
        t_start = wi * WINDOW_MS
        t_end = t_start + WINDOW_MS
        center_t, avg_speed, avg_x, avg_y = window_speeds[wi]

        # Count keystrokes in this window
        n_keys = sum(1 for kt in key_timestamps if t_start <= kt < t_end)
        kps = n_keys / (WINDOW_MS / 1000)  # keys per second

        # Decide whether this is a typing zone:
        # - Mouse truly still  → full typing score
        # - Mouse drifting slowly → reduced typing score (position less certain)
        mouse_is_still = avg_speed < MOUSE_STILL_PX_MS
        mouse_slow_enough = avg_speed < MOUSE_TYPING_PX_MS
        is_typing = mouse_slow_enough and kps >= TYPING_MIN_KPS

        if is_typing:
            # Score based on typing density; penalize if mouse is drifting
            base_score = min(kps / 10.0, 1.0) * WEIGHT_TYPING
            score = base_score if mouse_is_still else base_score * 0.7
            windows.append((center_t, score, avg_x, avg_y, "typing"))
        else:
            # Mouse settlement: look for deceleration (fast → slow)
            # Compare this window's speed to the previous window's speed
            if wi > 0:
                prev_speed = window_speeds[wi - 1][1]
                if prev_speed > 0 and avg_speed < prev_speed:
                    decel_ratio = prev_speed / max(avg_speed, 0.01)
                    if decel_ratio >= DECEL_MIN_RATIO:
                        # Score based on how dramatic the slowdown is
                        score = min(decel_ratio / 10.0, 1.0) * WEIGHT_MOUSE
                        # Use the CURRENT window's position (where cursor settled)
                        windows.append((center_t, score, avg_x, avg_y, "mouse"))
                        continue
            # No significant deceleration — still record for fallback
            windows.append((center_t, avg_speed * 0.1, avg_x, avg_y, "mouse"))

    if not windows:
        return []

    # ── 3. Find peaks per signal type ───────────────────────────────
    mouse_windows = [w for w in windows if w[4] == "mouse"]
    typing_windows = [w for w in windows if w[4] == "typing"]

    logger.info(
        "Windows: %d mouse, %d typing",
        len(mouse_windows), len(typing_windows),
    )

    peaks: List[WindowInfo] = []

    # Mouse settlement peaks: windows with high deceleration score
    if mouse_windows:
        m_scores = sorted(w[1] for w in mouse_windows)
        m_median = m_scores[len(m_scores) // 2]
        m_threshold = max(m_median * 2.0, WEIGHT_MOUSE * 0.15)
        for i, w in enumerate(mouse_windows):
            if w[1] < m_threshold:
                continue
            # Local maximum check within mouse windows
            left_ok = i == 0 or w[1] >= mouse_windows[i - 1][1]
            right_ok = i == len(mouse_windows) - 1 or w[1] >= mouse_windows[i + 1][1]
            if left_ok and right_ok:
                peaks.append(w)

    # Typing peaks: sustained typing runs (merge consecutive typing windows
    # into runs, take the center of each run)
    if typing_windows:
        runs: List[List[WindowInfo]] = []
        current_run: List[WindowInfo] = [typing_windows[0]]
        for tw in typing_windows[1:]:
            if tw[0] - current_run[-1][0] <= WINDOW_MS * 1.5:
                current_run.append(tw)
            else:
                runs.append(current_run)
                current_run = [tw]
        runs.append(current_run)

        for run in runs:
            # Pick the window with highest typing score in this run
            best = max(run, key=lambda w: w[1])
            peaks.append(best)

    # Click-cluster peaks: ≥2 clicks within a 3-second sliding window
    if click_events and len(click_events) >= CLICK_MIN_COUNT:
        sorted_clicks = sorted(click_events, key=lambda c: c.timestamp)
        i = 0
        used_up_to = -1.0  # avoid overlapping click clusters
        while i < len(sorted_clicks):
            # Collect all clicks within CLICK_WINDOW_MS of click[i]
            burst: List[ClickEvent] = [sorted_clicks[i]]
            j = i + 1
            while j < len(sorted_clicks) and sorted_clicks[j].timestamp - sorted_clicks[i].timestamp <= CLICK_WINDOW_MS:
                burst.append(sorted_clicks[j])
                j += 1

            if len(burst) >= CLICK_MIN_COUNT and sorted_clicks[i].timestamp > used_up_to:
                # Centroid of click positions (normalized to monitor)
                cx = sum(c.x for c in burst) / len(burst)
                cy = sum(c.y for c in burst) / len(burst)
                nx = max(0.0, min(1.0, (cx - mon_left) / mon_w))
                ny = max(0.0, min(1.0, (cy - mon_top) / mon_h))
                center_t = sum(c.timestamp for c in burst) / len(burst)
                # Score: more clicks = stronger signal (normalize: 5 clicks = max)
                score = min(len(burst) / 5.0, 1.0) * WEIGHT_CLICK
                peaks.append((center_t, score, nx, ny, "click"))
                used_up_to = burst[-1].timestamp  # skip past this burst
                i = j  # advance past the burst
            else:
                i += 1

    if not peaks:
        # Fallback: top-N windows by score regardless of type
        all_scored = sorted(windows, key=lambda w: w[1], reverse=True)
        peaks = all_scored[:max_clusters]

    # Log peak breakdown
    peak_types = {}
    for p in peaks:
        peak_types[p[4]] = peak_types.get(p[4], 0) + 1
    logger.info("Peaks: %s", peak_types)

    # ── 4. Cluster nearby peaks (spatial-aware) ────────────────────
    #
    # Two peaks merge into the same cluster when EITHER:
    #   a) they are within min_gap_ms of any peak already in the cluster, OR
    #   b) they share the same type (click / typing), are spatially close
    #      (< SPATIAL_MERGE_DIST), and within an extended time threshold.
    #
    # This prevents repeated zoom-out → zoom-in cycles when the user
    # clicks or types in the same area with small pauses.
    peaks.sort(key=lambda p: p[0])
    clusters: List[List[WindowInfo]] = []
    current_cluster: List[WindowInfo] = [peaks[0]]

    for p in peaks[1:]:
        should_merge = False
        for cp in current_cluster:
            gap = p[0] - cp[0]
            # (a) always merge if within the base time gap
            if gap < min_gap_ms:
                should_merge = True
                break
            # (b) extended merge for same-type, spatially close peaks
            if p[4] == cp[4] and p[4] in ("click", "typing"):
                dist = math.sqrt((p[2] - cp[2]) ** 2 + (p[3] - cp[3]) ** 2)
                ext_gap = CLICK_MERGE_GAP_MS if p[4] == "click" else TYPING_MERGE_GAP_MS
                if dist < SPATIAL_MERGE_DIST and gap < ext_gap:
                    should_merge = True
                    break

        if should_merge:
            current_cluster.append(p)
        else:
            clusters.append(current_cluster)
            current_cluster = [p]
    clusters.append(current_cluster)

    # Keep top N clusters by peak score
    def cluster_peak_score(c: List[WindowInfo]) -> float:
        return max(p[1] for p in c)

    clusters.sort(key=cluster_peak_score, reverse=True)
    clusters = clusters[:max_clusters]
    clusters.sort(key=lambda c: c[0][0])

    # ── 5. Generate keyframe pairs ──────────────────────────────────
    #
    # For each cluster we zoom in at the *start* of its activity and
    # zoom out after the *end* + a hold period.  The pan target is the
    # score-weighted centroid of the cluster, dampened so the viewport
    # doesn't jump excessively.
    #
    # When consecutive clusters are close in time, we stay zoomed in
    # and smoothly **pan** to the new location instead of zooming out
    # and back in.  This avoids disorienting zoom-out / zoom-in cycles
    # when actions happen across different parts of the screen.
    keyframes: List[ZoomKeyframe] = []

    # Pre-compute cluster info for boundary clamping
    cluster_info: List[dict] = []
    for cluster in clusters:
        best = max(cluster, key=lambda p: p[1])
        cluster_start = min(p[0] for p in cluster)
        cluster_end = max(p[0] for p in cluster)

        # Score-weighted centroid position (raw, un-dampened)
        total_score = sum(p[1] for p in cluster)
        if follow_cursor and total_score > 0:
            raw_x = sum(p[2] * p[1] for p in cluster) / total_score
            raw_y = sum(p[3] * p[1] for p in cluster) / total_score
        elif follow_cursor:
            raw_x, raw_y = best[2], best[3]
        else:
            raw_x, raw_y = 0.5, 0.5

        # Initial dampened pan (from center).  For chained clusters
        # this will be recomputed from the previous cluster's pan.
        pan_x, pan_y = _dampen_pan(raw_x, raw_y, zoom_level)

        label = best[4]
        # Anticipation: arrive ANTICIPATION_MS *before* the action starts,
        # so the viewer sees the trigger.  The transition must complete at
        # (cluster_start - ANTICIPATION_MS), so it starts one TRANSITION_MS
        # before that.
        zoom_in_time = max(0.0, cluster_start - TRANSITION_MS - ANTICIPATION_MS)

        # Hold duration depends on activity type
        if label == "typing":
            hold_ms = ZOOM_HOLD_TYPING_MS
            reason = "Typing activity detected"
        elif label == "click":
            hold_ms = ZOOM_HOLD_CLICK_MS
            reason = "Click cluster detected"
        else:
            hold_ms = ZOOM_HOLD_MOUSE_MS
            reason = "Cursor settled here"

        cluster_info.append({
            "start": cluster_start,
            "end": cluster_end,
            "zoom_in_time": zoom_in_time,
            "pan_x": pan_x,
            "pan_y": pan_y,
            "raw_x": raw_x,
            "raw_y": raw_y,
            "label": label,
            "hold_ms": hold_ms,
            "reason": reason,
        })

    # ── Build chains of clusters to pan between ────────────────────
    #
    # A "chain" is a sequence of clusters that are close enough to
    # stay zoomed in and just pan.  The camera zooms in at the start
    # of the first cluster and zooms out after the last.
    chains: List[List[int]] = []  # each chain is a list of cluster indices
    current_chain: List[int] = [0] if cluster_info else []

    for ci_idx in range(1, len(cluster_info)):
        prev_ci = cluster_info[current_chain[-1]]
        curr_ci = cluster_info[ci_idx]
        prev_end_with_hold = prev_ci["end"] + prev_ci["hold_ms"]
        gap = curr_ci["start"] - prev_end_with_hold

        if gap < PAN_MERGE_GAP_MS and len(current_chain) < MAX_CHAIN_LENGTH:
            # Close enough and chain not too long → stay zoomed, pan
            current_chain.append(ci_idx)
        else:
            chains.append(current_chain)
            current_chain = [ci_idx]
    if current_chain:
        chains.append(current_chain)

    # ── Generate keyframes from chains ─────────────────────────────
    for chain in chains:
        first_ci = cluster_info[chain[0]]
        last_ci = cluster_info[chain[-1]]

        # Zoom-in at the start of the first cluster
        zoom_in_time = first_ci["zoom_in_time"]
        kf_in = ZoomKeyframe.create(
            timestamp=zoom_in_time,
            zoom=zoom_level,
            x=first_ci["pan_x"],
            y=first_ci["pan_y"],
            duration=TRANSITION_MS,
            reason=first_ci["reason"],
        )
        keyframes.append(kf_in)

        # Pan keyframes between consecutive clusters in the chain.
        # Each pan target is computed relative to the previous cluster's
        # pan position so the camera only moves as far as needed.
        prev_pan_x = first_ci["pan_x"]
        prev_pan_y = first_ci["pan_y"]

        for i in range(1, len(chain)):
            prev_ci = cluster_info[chain[i - 1]]
            curr_ci = cluster_info[chain[i]]

            # Recompute this cluster's pan from the previous position
            curr_pan_x, curr_pan_y = _dampen_pan(
                curr_ci["raw_x"], curr_ci["raw_y"], zoom_level,
                from_x=prev_pan_x, from_y=prev_pan_y,
            )
            # Store updated pan for the next iteration
            curr_ci["pan_x"] = curr_pan_x
            curr_ci["pan_y"] = curr_pan_y

            # Duration proportional to pan distance, with min/max bounds
            dx = curr_pan_x - prev_pan_x
            dy = curr_pan_y - prev_pan_y
            dist = math.sqrt(dx * dx + dy * dy)
            pan_dur = min(
                PAN_TRANSITION_MAX_MS,
                max(PAN_TRANSITION_MS, int(dist * 1200)),
            )

            # Pan should complete ANTICIPATION_MS before the activity starts
            desired_arrive = curr_ci["start"] - ANTICIPATION_MS
            pan_time = max(
                prev_ci["end"],  # never start before the previous action ends
                desired_arrive - pan_dur,
            )

            # safety: don't go earlier than the chain zoom-in completion
            pan_time = max(zoom_in_time + TRANSITION_MS, pan_time)

            kf_pan = ZoomKeyframe.create(
                timestamp=pan_time,
                zoom=zoom_level,
                x=curr_pan_x,
                y=curr_pan_y,
                duration=pan_dur,
                reason=f"Pan to: {curr_ci['reason'].lower()}",
            )
            keyframes.append(kf_pan)
            prev_pan_x, prev_pan_y = curr_pan_x, curr_pan_y

        # Zoom-out after the last cluster's hold period
        zoom_out_time = last_ci["end"] + last_ci["hold_ms"]
        zoom_out_dur = TRANSITION_MS * 2  # zoom-out is slower

        if zoom_out_time > duration:
            zoom_out_time = duration

        kf_out = ZoomKeyframe.create(
            timestamp=zoom_out_time,
            zoom=1.0,
            x=0.5,
            y=0.5,
            duration=zoom_out_dur,
            reason=f"Zoom out after: {last_ci['reason'].lower()}",
        )
        keyframes.append(kf_out)

    keyframes.sort(key=lambda k: k.timestamp)
    return keyframes
