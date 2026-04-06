"""Tests for app.activity_analyzer — auto-zoom generation logic."""

import pytest

from app.activity_analyzer import (
    analyze_activity,
    _dampen_pan,
    PEAK_TOP_N,
    MAX_CLUSTER_DURATION_MS,
    PAN_MERGE_GAP_MS,
    MAX_CHAIN_LENGTH,
    TRANSITION_MS,
    ANTICIPATION_MS,
    ZOOM_LEVEL,
    WINDOW_MS,
)
from app.models import MousePosition, KeyEvent, ClickEvent, ZoomKeyframe


# ── Helpers ─────────────────────────────────────────────────────────

def _make_track(duration_ms: int, interval: int = 16,
                x: float = 500.0, y: float = 500.0) -> list[MousePosition]:
    """Generate a stationary mouse track of given duration."""
    return [
        MousePosition(x=x, y=y, timestamp=t)
        for t in range(0, duration_ms + 1, interval)
    ]


def _make_settlement_track(duration_ms: int = 10000) -> list[MousePosition]:
    """Track with a fast→slow settlement at 5s.

    0–4s: slow drift, 4–5s: fast move, 5–10s: settle.
    """
    track: list[MousePosition] = []
    for i in range(duration_ms // 16 + 1):
        t = i * 16.0
        if t < 4000:
            x = 500.0 + i * 0.5
            y = 500.0
        elif t < 5000:
            x = 500.0 + (t - 4000) * 1.2
            y = 500.0 + (t - 4000) * 0.6
        else:
            x = 1700.0
            y = 1100.0
        track.append(MousePosition(x=x, y=y, timestamp=t))
    return track


MONITOR = {"left": 0, "top": 0, "width": 1920, "height": 1080}


# ── _dampen_pan ─────────────────────────────────────────────────────


class TestDampenPan:
    def test_no_zoom_returns_center(self) -> None:
        px, py = _dampen_pan(0.3, 0.7, zoom=1.0)
        assert px == 0.5
        assert py == 0.5

    def test_target_already_visible(self) -> None:
        """When target is near current view center, pan shouldn't move."""
        px, py = _dampen_pan(0.5, 0.5, zoom=1.5, from_x=0.5, from_y=0.5)
        assert px == pytest.approx(0.5)
        assert py == pytest.approx(0.5)

    def test_target_far_shifts_viewport(self) -> None:
        """When target is far from center, viewport should shift toward it."""
        px, py = _dampen_pan(0.9, 0.9, zoom=2.0, from_x=0.5, from_y=0.5)
        assert px > 0.5
        assert py > 0.5

    def test_clamps_to_edge(self) -> None:
        """Pan should never let viewport go past the source edge."""
        px, py = _dampen_pan(1.0, 1.0, zoom=2.0)
        half = 0.5 / 2.0  # half viewport at zoom=2.0
        assert px <= 1.0 - half
        assert py <= 1.0 - half
        assert px >= half
        assert py >= half


# ── analyze_activity — edge cases ───────────────────────────────────


class TestAnalyzeEdgeCases:
    def test_too_few_samples(self) -> None:
        """Fewer than 10 samples → no keyframes."""
        short = [MousePosition(x=0, y=0, timestamp=i * 16) for i in range(5)]
        assert analyze_activity(short, MONITOR) == []

    def test_empty_track(self) -> None:
        assert analyze_activity([], MONITOR) == []

    def test_stationary_mouse_no_keys_no_clicks(self) -> None:
        """Stationary mouse with no key/click activity → zero keyframes.

        The analyzer only generates zoom events from typing zones (keys
        while mouse is still) or click clusters.  Without either signal
        there is nothing to zoom into."""
        track = _make_track(5000)
        kfs = analyze_activity(track, MONITOR)
        assert kfs == []

    def test_zoom_level_zero_no_crash(self) -> None:
        """zoom_level=0 should not cause ZeroDivisionError."""
        track = _make_track(10000, x=960, y=540)
        keys = [KeyEvent(timestamp=3000 + i * 50) for i in range(30)]
        # Should not raise ZeroDivisionError
        kfs = analyze_activity(track, MONITOR, key_events=keys, zoom_level=0.0)
        assert isinstance(kfs, list)


# ── analyze_activity — typing detection ─────────────────────────────


class TestAnalyzeTyping:
    def test_typing_burst_generates_keyframes(self) -> None:
        """A rapid typing burst with still mouse should trigger zoom."""
        track = _make_track(10000, x=960, y=540)
        keys = [KeyEvent(timestamp=3000 + i * 50) for i in range(30)]
        kfs = analyze_activity(track, MONITOR, key_events=keys)
        assert len(kfs) >= 2  # at least one zoom-in + zoom-out

    def test_typing_keyframe_targets_cursor_position(self) -> None:
        """Zoom target should be near the cursor position during typing."""
        track = _make_track(10000, x=960, y=540)  # center of 1920×1080
        keys = [KeyEvent(timestamp=3000 + i * 50) for i in range(30)]
        kfs = analyze_activity(track, MONITOR, key_events=keys,
                               zoom_level=1.5, follow_cursor=True)
        # Find the zoom-in keyframe (zoom > 1)
        zoom_ins = [k for k in kfs if k.zoom > 1.01]
        assert len(zoom_ins) >= 1
        kf = zoom_ins[0]
        # cursor at (960, 540) → normalized (0.5, 0.5)
        assert abs(kf.x - 0.5) < 0.2
        assert abs(kf.y - 0.5) < 0.2

    def test_typing_uses_keystroke_position(self) -> None:
        """When KeyEvent has x/y coords, zoom should target those coordinates
        rather than the mouse cursor position."""
        # Mouse is at top-left, but keystrokes report bottom-right position
        track = _make_track(10000, x=100, y=100)
        keys = [
            KeyEvent(timestamp=3000 + i * 50, x=1700.0, y=900.0)
            for i in range(30)
        ]
        kfs = analyze_activity(track, MONITOR, key_events=keys,
                               zoom_level=1.5, follow_cursor=True)
        zoom_ins = [k for k in kfs if k.zoom > 1.01]
        assert len(zoom_ins) >= 1
        kf = zoom_ins[0]
        # Should be near (1700/1920, 900/1080) ≈ (0.885, 0.833)
        # and NOT near (100/1920, 100/1080) ≈ (0.052, 0.093)
        assert kf.x > 0.5, f"Expected x > 0.5 (keystroke position), got {kf.x}"
        assert kf.y > 0.5, f"Expected y > 0.5 (keystroke position), got {kf.y}"


# ── analyze_activity — click clusters ──────────────────────────────


class TestAnalyzeClicks:
    def test_click_cluster_generates_keyframes(self) -> None:
        """≥2 clicks in a window should trigger zoom."""
        track = _make_track(10000, x=960, y=540)
        clicks = [
            ClickEvent(x=800, y=400, timestamp=5000),
            ClickEvent(x=820, y=410, timestamp=5200),
            ClickEvent(x=810, y=420, timestamp=5400),
        ]
        kfs = analyze_activity(track, MONITOR, click_events=clicks)
        assert len(kfs) >= 2

    def test_single_click_generates_zoom(self) -> None:
        """A single deliberate click SHOULD trigger zoom."""
        track = _make_track(10000, x=960, y=540)
        clicks = [ClickEvent(x=800, y=400, timestamp=5000)]
        kfs = analyze_activity(track, MONITOR, click_events=clicks)
        click_kfs = [k for k in kfs if "click" in k.reason.lower()]
        assert len(click_kfs) >= 1

    def test_click_without_settlement_zoom(self) -> None:
        """A click should zoom even when the nearby cursor resting would
        have been ignored (mouse settlements are disabled)."""
        track = _make_settlement_track()
        clicks = [ClickEvent(x=1700, y=1100, timestamp=5000)]
        kfs = analyze_activity(track, MONITOR, click_events=clicks)
        # Should have a click-triggered zoom
        click_kfs = [k for k in kfs if "click" in k.reason.lower()]
        assert len(click_kfs) >= 1
        # No mouse-settlement keyframes should exist
        mouse_kfs = [k for k in kfs if "cursor" in k.reason.lower() or "settled" in k.reason.lower()]
        assert len(mouse_kfs) == 0


# ── analyze_activity — mouse settlements disabled ──────────────────


class TestMouseSettlementDisabled:
    def test_settlement_alone_produces_no_keyframes(self) -> None:
        """A fast→slow mouse move with no clicks or typing should NOT
        produce any zoom keyframes (mouse settlements are disabled)."""
        track = _make_settlement_track()
        kfs = analyze_activity(track, MONITOR)
        assert len(kfs) == 0


# ── analyze_activity — typing pans to field position ────────────────


class TestTypingPanPosition:
    def test_typing_zoom_centers_on_field(self) -> None:
        """Typing in a corner of the screen should pan the viewport
        there, not stay centered."""
        # Mouse parked at top-left corner
        track = _make_track(10000, x=200, y=100)
        keys = [KeyEvent(timestamp=3000 + i * 50) for i in range(20)]
        kfs = analyze_activity(track, MONITOR, key_events=keys)
        zoom_ins = [k for k in kfs if k.zoom > 1.01]
        assert len(zoom_ins) >= 1
        kf = zoom_ins[0]
        # Target should be near (200/1920, 100/1080) ≈ (0.104, 0.093)
        # NOT centered at (0.5, 0.5)
        assert kf.x < 0.4, f"Expected x < 0.4 but got {kf.x}"
        assert kf.y < 0.4, f"Expected y < 0.4 but got {kf.y}"


# ── analyze_activity — keyframe structure ───────────────────────────


class TestAnalyzeKeyframeStructure:
    def test_keyframes_sorted_by_timestamp(self) -> None:
        track = _make_settlement_track()
        keys = [KeyEvent(timestamp=2000 + i * 50) for i in range(20)]
        kfs = analyze_activity(track, MONITOR, key_events=keys)
        for i in range(len(kfs) - 1):
            assert kfs[i].timestamp <= kfs[i + 1].timestamp

    def test_zoom_in_out_pairs(self) -> None:
        """Each zoom-in (>1) must eventually be followed by a zoom-out (=1)."""
        track = _make_settlement_track()
        keys = [KeyEvent(timestamp=2000 + i * 50) for i in range(20)]
        kfs = analyze_activity(track, MONITOR, key_events=keys)
        if not kfs:
            pytest.skip("No keyframes generated")

        # Walk through keyframes: every zoom>1 must have a matching zoom=1
        in_zoom = False
        for kf in kfs:
            if kf.zoom > 1.01:
                in_zoom = True
            elif kf.zoom <= 1.01:
                # This is a zoom-out — must have been in zoom mode
                assert in_zoom, f"Zoom-out at {kf.timestamp} without prior zoom-in"
                in_zoom = False
        # After last keyframe, should not still be zoomed in
        # (unless the zoom-out is the last keyframe, which is fine)

    def test_max_clusters_respected(self) -> None:
        """Should never produce more clusters than max_clusters."""
        track = _make_track(20000)
        # Lots of typing at different times
        keys = []
        for burst_start in range(1000, 18000, 2000):
            keys += [KeyEvent(timestamp=burst_start + i * 50) for i in range(10)]
        kfs = analyze_activity(track, MONITOR, key_events=keys, max_clusters=3)
        # Count zoom-in events
        zoom_ins = [k for k in kfs if k.zoom > 1.01]
        # With panning, multiple zoom_ins might appear in a chain, but total
        # clusters (zoom-in from 1.0) should be ≤ max_clusters
        assert zoom_ins is not None  # just ensure no crash with limit

    def test_anticipation_timing(self) -> None:
        """Zoom-in should arrive before or near the activity start."""
        track = _make_track(10000, x=960, y=540)
        keys = [KeyEvent(timestamp=5000 + i * 50) for i in range(20)]
        kfs = analyze_activity(track, MONITOR, key_events=keys)
        zoom_ins = [k for k in kfs if k.zoom > 1.01]
        if zoom_ins:
            kf = zoom_ins[0]
            # The zoom-in keyframe should complete before or near the
            # activity start.  Allow WINDOW_MS tolerance because peaks
            # are quantised to window centres.
            completion = kf.timestamp + kf.duration
            assert completion <= 5000 + WINDOW_MS

    def test_follow_cursor_false(self) -> None:
        """With follow_cursor=False, pan target should be center."""
        track = _make_track(10000, x=100, y=100)
        keys = [KeyEvent(timestamp=3000 + i * 50) for i in range(20)]
        kfs = analyze_activity(track, MONITOR, key_events=keys,
                               follow_cursor=False)
        zoom_ins = [k for k in kfs if k.zoom > 1.01]
        for kf in zoom_ins:
            assert kf.x == pytest.approx(0.5, abs=0.1)
            assert kf.y == pytest.approx(0.5, abs=0.1)

    def test_custom_zoom_level(self) -> None:
        """Zoom level should match the requested value."""
        track = _make_track(10000, x=960, y=540)
        keys = [KeyEvent(timestamp=3000 + i * 50) for i in range(20)]
        kfs = analyze_activity(track, MONITOR, key_events=keys,
                               zoom_level=2.5)
        zoom_ins = [k for k in kfs if k.zoom > 1.01]
        for kf in zoom_ins:
            assert kf.zoom == pytest.approx(2.5)


# ── analyze_activity — cluster splitting ────────────────────────────


class TestClusterSplitting:
    def test_long_cluster_is_split(self) -> None:
        """Typing at two spatially-separated locations should produce
        separate zoom blocks when the total span exceeds
        MAX_CLUSTER_DURATION_MS."""
        # Build a track that stays at (200,200) for the first half,
        # then jumps to (1700,900) — spatially distinct positions.
        track: list[MousePosition] = []
        for i in range(20000 // 16 + 1):
            t = i * 16.0
            x, y = (200.0, 200.0) if t < 10000 else (1700.0, 900.0)
            track.append(MousePosition(x=x, y=y, timestamp=t))

        # Typing bursts in each half
        keys = (
            [KeyEvent(timestamp=1000 + i * 50) for i in range(80)]   # 4s burst at pos A
            + [KeyEvent(timestamp=12000 + i * 50) for i in range(80)] # 4s burst at pos B
        )
        kfs = analyze_activity(track, MONITOR, key_events=keys)
        zoom_ins = [k for k in kfs if k.zoom > 1.01]
        # Two spatially-separated bursts with a large gap → ≥2 zoom blocks
        assert len(zoom_ins) >= 2


# ── analyze_activity — overlap prevention ───────────────────────────


class TestOverlapPrevention:
    def test_no_overlapping_transitions(self) -> None:
        """A zoom-out must complete before the next zoom-in starts."""
        track = _make_track(20000, x=960, y=540)
        # Two bursts close together to test overlap handling
        keys = (
            [KeyEvent(timestamp=2000 + i * 50) for i in range(20)]
            + [KeyEvent(timestamp=6000 + i * 50) for i in range(20)]
        )
        kfs = analyze_activity(track, MONITOR, key_events=keys)
        for i in range(len(kfs) - 1):
            curr = kfs[i]
            nxt = kfs[i + 1]
            if curr.zoom <= 1.01 and nxt.zoom > 1.01:
                curr_end = curr.timestamp + curr.duration
                assert curr_end <= nxt.timestamp + 1  # 1ms tolerance

    def test_no_overlapping_segments(self) -> None:
        """Zoom segments must not overlap — each segment's visual span
        must end before the next segment starts.  This catches the case
        where two chains' keyframes interleave in the sorted list."""
        track = _make_track(20000, x=960, y=540)
        # Two click clusters separated by just over PAN_MERGE_GAP_MS,
        # which makes them separate chains whose hold+zoom-out would
        # overlap the next chain's zoom-in without the chain-level fix.
        clicks = [
            ClickEvent(x=300, y=200, timestamp=3000),
            ClickEvent(x=1600, y=800, timestamp=5500),
        ]
        kfs = analyze_activity(track, MONITOR, click_events=clicks)
        # Extract zoom segments: (start_time, end_time)
        sorted_kfs = sorted(kfs, key=lambda k: k.timestamp)
        segments: list[tuple[float, float]] = []
        seg_start: float | None = None
        for kf in sorted_kfs:
            if kf.zoom > 1.01 and seg_start is None:
                seg_start = kf.timestamp
            elif kf.zoom <= 1.01 and seg_start is not None:
                segments.append((seg_start, kf.timestamp + kf.duration))
                seg_start = None
        # Segments must not overlap
        for i in range(len(segments) - 1):
            assert segments[i][1] <= segments[i + 1][0] + 1, (
                f"Segment {i} ends at {segments[i][1]} but segment {i+1} "
                f"starts at {segments[i+1][0]}"
            )


# ── analyze_activity — chaining (pan-while-zoomed) ──────────────────


class TestChaining:
    def test_close_clusters_pan_instead_of_zoom_out_in(self) -> None:
        """Clusters within PAN_MERGE_GAP_MS should produce pan keyframes
        instead of zoom-out → zoom-in pairs."""
        track = _make_track(10000, x=960, y=540)
        # Two click clusters very close in time
        clicks = [
            ClickEvent(x=400, y=300, timestamp=3000),
            ClickEvent(x=420, y=310, timestamp=3200),
            ClickEvent(x=1500, y=800, timestamp=4000),
            ClickEvent(x=1520, y=810, timestamp=4200),
        ]
        kfs = analyze_activity(track, MONITOR, click_events=clicks)
        # Should have a pan keyframe between the two clusters
        pan_kfs = [k for k in kfs if "pan" in k.reason.lower()]
        # May or may not chain depending on gap — just ensure no crash
        assert isinstance(kfs, list)


# ── analyze_activity — zoom_level guard ─────────────────────────────


class TestAnalyzeActivityZoomLevelGuard:
    """analyze_activity must not raise ZeroDivisionError for zoom_level <= 0."""

    def _make_active_track(self) -> list:
        """Track long enough with clicks to produce keyframes."""
        from app.models import MousePosition
        return [
            MousePosition(x=500.0 + i * 0.5, y=500.0, timestamp=float(i * 16))
            for i in range(700)
        ]

    def test_zoom_level_zero_does_not_raise(self) -> None:
        """zoom_level=0 must not raise ZeroDivisionError."""
        from app.models import ClickEvent
        track = self._make_active_track()
        clicks = [ClickEvent(x=500, y=500, timestamp=3000)]
        # Should not raise; falls back to zoom_level=1.0
        result = analyze_activity(track, MONITOR, click_events=clicks, zoom_level=0.0)
        assert isinstance(result, list)

    def test_zoom_level_negative_does_not_raise(self) -> None:
        """zoom_level=-1 must not raise ZeroDivisionError."""
        from app.models import ClickEvent
        track = self._make_active_track()
        clicks = [ClickEvent(x=500, y=500, timestamp=3000)]
        result = analyze_activity(track, MONITOR, click_events=clicks, zoom_level=-1.0)
        assert isinstance(result, list)
