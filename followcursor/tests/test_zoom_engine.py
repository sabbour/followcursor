"""Tests for app.zoom_engine — interpolation, undo/redo."""

import pytest

from app.zoom_engine import ease_out, smooth_step, ZoomEngine, MAX_UNDO
from app.models import ZoomKeyframe


# ── ease_out ────────────────────────────────────────────────────────


class TestEaseOut:
    def test_boundaries(self) -> None:
        assert ease_out(0.0) == pytest.approx(0.0)
        assert ease_out(1.0) == pytest.approx(1.0)

    def test_midpoint_above_linear(self) -> None:
        """Ease-out should be above linear at t=0.5 (fast start)."""
        assert ease_out(0.5) > 0.5

    def test_monotonic(self) -> None:
        """ease_out must be strictly increasing on [0, 1]."""
        prev = ease_out(0.0)
        for i in range(1, 101):
            t = i / 100.0
            curr = ease_out(t)
            assert curr > prev, f"Not monotonic at t={t}"
            prev = curr

    def test_quintic_value(self) -> None:
        """Verify the formula: 1 - (1-t)^5."""
        t = 0.3
        expected = 1.0 - (0.7 ** 5)
        assert ease_out(t) == pytest.approx(expected)

    def test_smooth_step_alias(self) -> None:
        assert smooth_step is ease_out


# ── ZoomEngine — basic operations ───────────────────────────────────


class TestZoomEngineBasics:
    def test_initial_state(self) -> None:
        engine = ZoomEngine()
        assert engine.keyframes == []
        assert engine.current_zoom == 1.0
        assert engine.current_pan_x == 0.5
        assert engine.current_pan_y == 0.5

    def test_compute_at_empty(self) -> None:
        engine = ZoomEngine()
        z, px, py = engine.compute_at(500)
        assert z == 1.0
        assert px == 0.5
        assert py == 0.5

    def test_add_keyframe_sorts(self) -> None:
        engine = ZoomEngine()
        kf_late = ZoomKeyframe.create(timestamp=2000, zoom=1.0)
        kf_early = ZoomKeyframe.create(timestamp=500, zoom=1.5)
        engine.add_keyframe(kf_late)
        engine.add_keyframe(kf_early)
        assert engine.keyframes[0].timestamp == 500
        assert engine.keyframes[1].timestamp == 2000

    def test_remove_keyframe(self) -> None:
        engine = ZoomEngine()
        kf = ZoomKeyframe.create(timestamp=100, zoom=1.5)
        engine.add_keyframe(kf)
        engine.remove_keyframe(kf.id)
        assert len(engine.keyframes) == 0

    def test_remove_nonexistent(self) -> None:
        engine = ZoomEngine()
        kf = ZoomKeyframe.create(timestamp=100, zoom=1.5)
        engine.add_keyframe(kf)
        engine.remove_keyframe("no-such-id")
        assert len(engine.keyframes) == 1

    def test_clear(self) -> None:
        engine = ZoomEngine()
        engine.add_keyframe(ZoomKeyframe.create(timestamp=100, zoom=1.5))
        engine.current_zoom = 2.0
        engine.clear()
        assert engine.keyframes == []
        assert engine.current_zoom == 1.0
        assert engine.current_pan_x == 0.5


# ── ZoomEngine — compute_at interpolation ───────────────────────────


class TestZoomEngineInterpolation:
    def test_before_first_keyframe(self) -> None:
        """Before any keyframe, state should be default."""
        engine = ZoomEngine()
        engine.add_keyframe(ZoomKeyframe.create(timestamp=1000, zoom=1.5))
        z, px, py = engine.compute_at(500)
        assert z == 1.0
        assert px == 0.5
        assert py == 0.5

    def test_at_keyframe_start(self) -> None:
        """At the exact keyframe timestamp, transition is 0% complete."""
        engine = ZoomEngine()
        engine.add_keyframe(ZoomKeyframe.create(timestamp=1000, zoom=2.0, duration=600))
        z, _, _ = engine.compute_at(1000)
        # progress = 0 → eased = 0 → zoom still at previous (1.0)
        assert z == pytest.approx(1.0)

    def test_after_transition_complete(self) -> None:
        """After transition duration, state should be at target."""
        engine = ZoomEngine()
        engine.add_keyframe(
            ZoomKeyframe.create(timestamp=1000, zoom=2.0, x=0.3, y=0.7, duration=600)
        )
        z, px, py = engine.compute_at(1600)  # 1000 + 600
        assert z == pytest.approx(2.0)
        assert px == pytest.approx(0.3)
        assert py == pytest.approx(0.7)

    def test_well_after_transition(self) -> None:
        """Way past the transition, values remain at target."""
        engine = ZoomEngine()
        engine.add_keyframe(
            ZoomKeyframe.create(timestamp=1000, zoom=1.5, duration=600)
        )
        z, _, _ = engine.compute_at(5000)
        assert z == pytest.approx(1.5)

    def test_mid_transition(self) -> None:
        """During transition, zoom should be between prev and target."""
        engine = ZoomEngine()
        engine.add_keyframe(
            ZoomKeyframe.create(timestamp=1000, zoom=2.0, duration=600)
        )
        z, _, _ = engine.compute_at(1300)  # 50% through
        assert 1.0 < z < 2.0

    def test_zoom_in_then_out(self, zoom_in_out_pair: list[ZoomKeyframe]) -> None:
        """After zoom-out transition completes, zoom should be back to 1.0."""
        engine = ZoomEngine()
        for kf in zoom_in_out_pair:
            engine.add_keyframe(kf)

        # During zoom-in hold (after transition)
        z, _, _ = engine.compute_at(1800)
        assert z == pytest.approx(1.5)

        # After zoom-out completion (4000 + 1200 = 5200)
        z, px, py = engine.compute_at(5200)
        assert z == pytest.approx(1.0)
        assert px == pytest.approx(0.5)
        assert py == pytest.approx(0.5)

    def test_update_caches_result(self) -> None:
        engine = ZoomEngine()
        engine.add_keyframe(
            ZoomKeyframe.create(timestamp=0, zoom=2.0, duration=0)
        )
        engine.update(100)
        assert engine.current_zoom == pytest.approx(2.0)

    def test_zero_duration_snaps(self) -> None:
        """Duration=0 should snap immediately to the target."""
        engine = ZoomEngine()
        engine.add_keyframe(
            ZoomKeyframe.create(timestamp=100, zoom=3.0, duration=0)
        )
        z, _, _ = engine.compute_at(100)
        assert z == pytest.approx(3.0)

    def test_pan_interpolation(self) -> None:
        """Pan coordinates should interpolate between keyframes."""
        engine = ZoomEngine()
        engine.add_keyframe(
            ZoomKeyframe.create(timestamp=0, zoom=1.5, x=0.2, y=0.3, duration=0)
        )
        engine.add_keyframe(
            ZoomKeyframe.create(timestamp=1000, zoom=1.5, x=0.8, y=0.9, duration=1000)
        )
        # At midpoint of second transition
        _, px, py = engine.compute_at(1500)
        assert 0.2 < px < 0.8
        assert 0.3 < py < 0.9


# ── ZoomEngine — undo / redo ────────────────────────────────────────


class TestZoomEngineUndoRedo:
    def test_undo_restores_state(self) -> None:
        engine = ZoomEngine()
        kf = ZoomKeyframe.create(timestamp=100, zoom=1.5)
        engine.push_undo()
        engine.add_keyframe(kf)
        assert len(engine.keyframes) == 1
        assert engine.undo()
        assert len(engine.keyframes) == 0

    def test_redo_restores_undone(self) -> None:
        engine = ZoomEngine()
        engine.push_undo()
        engine.add_keyframe(ZoomKeyframe.create(timestamp=100, zoom=1.5))
        engine.undo()
        assert len(engine.keyframes) == 0
        assert engine.redo()
        assert len(engine.keyframes) == 1

    def test_undo_empty_returns_false(self) -> None:
        engine = ZoomEngine()
        assert not engine.undo()

    def test_redo_empty_returns_false(self) -> None:
        engine = ZoomEngine()
        assert not engine.redo()

    def test_can_undo_redo_properties(self) -> None:
        engine = ZoomEngine()
        assert not engine.can_undo
        assert not engine.can_redo
        engine.push_undo()
        engine.add_keyframe(ZoomKeyframe.create(timestamp=0, zoom=1.5))
        assert engine.can_undo
        engine.undo()
        assert engine.can_redo

    def test_push_undo_clears_redo(self) -> None:
        engine = ZoomEngine()
        engine.push_undo()
        engine.add_keyframe(ZoomKeyframe.create(timestamp=0, zoom=1.5))
        engine.undo()
        assert engine.can_redo
        engine.push_undo()  # new edit branch → redo cleared
        assert not engine.can_redo

    def test_max_undo_depth(self) -> None:
        engine = ZoomEngine()
        for i in range(MAX_UNDO + 10):
            engine.push_undo()
            engine.add_keyframe(ZoomKeyframe.create(timestamp=i * 100, zoom=1.5))
        assert len(engine._undo_stack) == MAX_UNDO

    def test_clear_history(self) -> None:
        engine = ZoomEngine()
        engine.push_undo()
        engine.add_keyframe(ZoomKeyframe.create(timestamp=0, zoom=1.5))
        engine.clear_history()
        assert not engine.can_undo
        assert not engine.can_redo

    def test_undo_deep_copies(self) -> None:
        """Undo snapshots must be independent copies — mutating the engine
        after push_undo shouldn't change the snapshot."""
        engine = ZoomEngine()
        kf = ZoomKeyframe.create(timestamp=100, zoom=1.5)
        engine.add_keyframe(kf)
        engine.push_undo()
        engine.keyframes[0] = ZoomKeyframe.create(timestamp=999, zoom=3.0)
        engine.undo()
        assert engine.keyframes[0].timestamp == 100
