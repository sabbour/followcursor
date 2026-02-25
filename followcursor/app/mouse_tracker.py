"""Mouse position tracker — polls cursor position at 60 Hz via Win32.

Uses ``GetCursorPos`` for **physical pixel** coordinates (not DPI-scaled)
so they match the capture APIs (mss, WGC, PrintWindow).  Runs on a
``QTimer`` in the main thread.
"""

import sys
import time
from typing import List

from PySide6.QtCore import QObject, QTimer

from .models import MousePosition

# Use Win32 GetCursorPos for physical pixel coordinates.
# QCursor.pos() returns logical (DPI-scaled) coordinates in Qt 6,
# but mss and Win32 capture APIs return physical pixel coordinates.
if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes as wintypes


def _get_physical_cursor_pos() -> tuple[int, int]:
    """Return the cursor position in physical screen pixels via Win32."""
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


class MouseTracker(QObject):
    """QTimer-based cursor poller that records :class:`MousePosition` samples.

    The polling interval defaults to 16 ms (~60 Hz).  All timestamps
    are relative to a shared epoch so they align with keyboard and
    click trackers.
    """

    def __init__(self, interval_ms: int = 16, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._interval = interval_ms
        self._start_time: float = 0.0
        self._positions: List[MousePosition] = []

    def start(self, start_ms: float = 0.0) -> None:
        """Begin polling cursor position.

        *start_ms* — shared epoch (``time.time() * 1000``) so all trackers
        use the same time base.
        """
        self._start_time = start_ms if start_ms > 0 else time.time() * 1000
        self._positions.clear()
        self._timer.start(self._interval)

    def stop(self) -> List[MousePosition]:
        """Stop polling and return the collected position samples."""
        self._timer.stop()
        return list(self._positions)

    def _poll(self) -> None:
        px, py = _get_physical_cursor_pos()
        mp = MousePosition(
            x=px,
            y=py,
            timestamp=time.time() * 1000 - self._start_time,
        )
        self._positions.append(mp)
