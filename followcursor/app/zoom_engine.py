"""Zoom engine — manages keyframes and interpolates zoom/pan state.

The engine holds an ordered list of :class:`ZoomKeyframe` objects and
computes the current ``(zoom, pan_x, pan_y)`` at any point in time
using quintic ease-out interpolation.  It also maintains an undo/redo
stack (deep-copy snapshots, max 50 entries).
"""

import copy
from typing import List, Tuple
from .models import ZoomKeyframe


def ease_out(t: float) -> float:
    """Quintic ease-out — fast start, decelerates asymptotically to zero.

    f(t) = 1 - (1-t)⁵

    The fifth-power curve gives a very pronounced deceleration at the
    end of the transition: roughly 80% of the movement happens in the
    first 40% of the duration, and the remaining 20% stretches out
    into a smooth, almost-motionless arrival.
    """
    inv = 1.0 - t
    return 1.0 - inv * inv * inv * inv * inv


# Keep the old name as an alias for any external callers
smooth_step = ease_out


MAX_UNDO = 50  # maximum undo history depth


class ZoomEngine:
    """Stateful zoom/pan interpolator with undo/redo support.

    Keyframes are kept sorted by timestamp.  ``compute_at(time_ms)``
    finds the most recent keyframe and eases from the previous state
    to the target over ``keyframe.duration`` milliseconds.
    """
    def __init__(self) -> None:
        self.keyframes: List[ZoomKeyframe] = []
        self.current_zoom: float = 1.0
        self.current_pan_x: float = 0.5
        self.current_pan_y: float = 0.5

        # Undo / redo stacks — each entry is a deep-copied keyframe list
        self._undo_stack: List[List[ZoomKeyframe]] = []
        self._redo_stack: List[List[ZoomKeyframe]] = []

    # ── snapshot helpers ────────────────────────────────────────────

    def _snapshot(self) -> List[ZoomKeyframe]:
        """Return a deep copy of the current keyframe list."""
        return copy.deepcopy(self.keyframes)

    def push_undo(self) -> None:
        """Save the current state onto the undo stack.

        Call this *before* any mutation so the previous state can be
        restored.  Clears the redo stack (new edit branch).
        """
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> bool:
        """Restore the previous keyframe state.  Returns True if successful."""
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        self.keyframes = self._undo_stack.pop()
        return True

    def redo(self) -> bool:
        """Re-apply the last undone change.  Returns True if successful."""
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        self.keyframes = self._redo_stack.pop()
        return True

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def clear_history(self) -> None:
        """Discard all undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    def add_keyframe(self, kf: ZoomKeyframe) -> None:
        """Insert a keyframe, keeping the list sorted by timestamp."""
        self.keyframes.append(kf)
        self.keyframes.sort(key=lambda k: k.timestamp)

    def remove_keyframe(self, kf_id: str) -> None:
        """Remove a keyframe by its unique ID."""
        self.keyframes = [kf for kf in self.keyframes if kf.id != kf_id]

    def clear(self) -> None:
        """Remove all keyframes and reset zoom/pan to defaults."""
        self.keyframes.clear()
        self.current_zoom = 1.0
        self.current_pan_x = 0.5
        self.current_pan_y = 0.5

    def compute_at(self, time_ms: float) -> Tuple[float, float, float]:
        """Returns (zoom, pan_x, pan_y) at given time."""
        if not self.keyframes:
            return 1.0, 0.5, 0.5

        active_kf = None
        active_idx = -1
        for i in range(len(self.keyframes) - 1, -1, -1):
            if time_ms >= self.keyframes[i].timestamp:
                active_kf = self.keyframes[i]
                active_idx = i
                break

        if active_kf is None:
            return 1.0, 0.5, 0.5

        elapsed = time_ms - active_kf.timestamp
        progress = (
            min(elapsed / active_kf.duration, 1.0) if active_kf.duration > 0 else 1.0
        )
        eased = ease_out(progress)

        prev_zoom = self.keyframes[active_idx - 1].zoom if active_idx > 0 else 1.0
        prev_x = self.keyframes[active_idx - 1].x if active_idx > 0 else 0.5
        prev_y = self.keyframes[active_idx - 1].y if active_idx > 0 else 0.5

        zoom = prev_zoom + (active_kf.zoom - prev_zoom) * eased
        pan_x = prev_x + (active_kf.x - prev_x) * eased
        pan_y = prev_y + (active_kf.y - prev_y) * eased

        return zoom, pan_x, pan_y

    def update(self, time_ms: float) -> None:
        """Evaluate zoom state at *time_ms* and cache the result.

        Convenience wrapper around ``compute_at()`` that stores the
        result in ``current_zoom``, ``current_pan_x``, ``current_pan_y``.
        """
        self.current_zoom, self.current_pan_x, self.current_pan_y = self.compute_at(
            time_ms
        )
