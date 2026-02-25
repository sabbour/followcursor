"""Mouse click tracker — records click positions via a Win32 low-level hook.

Records timestamp and screen coordinates of left/right mouse-button-down events.
Runs the hook in a dedicated thread to avoid blocking the Qt event loop.
"""

import logging
import sys
import time
import ctypes
import ctypes.wintypes as wintypes
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from .models import ClickEvent

logger = logging.getLogger(__name__)

# Win32 constants
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_QUIT = 0x0012

if sys.platform == "win32":
    class MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt", wintypes.POINT),
            ("mouseData", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    # Use WINFUNCTYPE with proper pointer-sized types for 64-bit compat
    HOOKPROC = ctypes.WINFUNCTYPE(
        wintypes.LPARAM,   # LRESULT (pointer-sized)
        ctypes.c_int,      # nCode
        wintypes.WPARAM,   # wParam (pointer-sized)
        wintypes.LPARAM,   # lParam (pointer-sized)
    )


class _MouseHookThread(QThread):
    """Runs a Win32 message loop with a low-level mouse hook."""

    click_detected = Signal(int, int, float)  # x, y screen coordinates, timestamp (ms)

    def __init__(self, start_ms: float = 0.0, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread_id: int = 0
        self._hook = None
        self._start_ms = start_ms
        self._proc = None  # prevent GC of the callback

    def run(self) -> None:
        if sys.platform != "win32":
            return

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        # Set argtypes/restype for 64-bit pointer compatibility
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD
        ]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK

        user32.CallNextHookEx.argtypes = [
            wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        ]
        user32.CallNextHookEx.restype = wintypes.LPARAM

        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL

        start_ms = self._start_ms

        def low_level_handler(n_code, w_param, l_param):
            try:
                if n_code >= 0 and w_param in (WM_LBUTTONDOWN, WM_RBUTTONDOWN):
                    ts = time.time() * 1000 - start_ms
                    # Cast the raw LPARAM integer to a pointer to MSLLHOOKSTRUCT
                    info = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    self.click_detected.emit(info.pt.x, info.pt.y, ts)
            except Exception:
                logger.exception("Error in mouse click hook callback")
            return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

        self._proc = HOOKPROC(low_level_handler)
        self._hook = user32.SetWindowsHookExW(
            WH_MOUSE_LL, self._proc, None, 0
        )

        # Pump messages so the hook receives events
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None

    def request_stop(self) -> None:
        if self._thread_id and sys.platform == "win32":
            ctypes.windll.user32.PostThreadMessageW(
                self._thread_id, WM_QUIT, 0, 0
            )


class ClickTracker(QObject):
    """Records positions and timestamps of mouse clicks during a recording."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: Optional[_MouseHookThread] = None
        self._events: List[ClickEvent] = []
        self._start_time: float = 0.0

    def start(self, start_ms: float = 0.0) -> None:
        """Begin tracking mouse clicks.

        *start_ms* — shared epoch (``time.time() * 1000``) so all trackers
        use the same time base.
        """
        if sys.platform != "win32":
            return
        self._events.clear()
        self._start_time = start_ms if start_ms > 0 else time.time() * 1000
        self._thread = _MouseHookThread(start_ms=self._start_time, parent=self)
        self._thread.click_detected.connect(self._on_click)
        self._thread.start()

    def stop(self) -> List[ClickEvent]:
        """Stop tracking and return collected events."""
        if self._thread is not None:
            self._thread.request_stop()
            self._thread.wait(2000)
            self._thread = None
        result = list(self._events)
        self._events.clear()
        return result

    def _on_click(self, x: int, y: int, ts: float) -> None:
        self._events.append(ClickEvent(x=float(x), y=float(y), timestamp=ts))

    @property
    def events(self) -> List[ClickEvent]:
        return list(self._events)
