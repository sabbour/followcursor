"""Keyboard activity tracker — counts keystrokes via a Win32 low-level hook.

Only records *timestamps* of key-down events (no key identity) for privacy.
Runs the hook in a dedicated thread to avoid blocking the Qt event loop.
"""

import logging
import sys
import time
import ctypes
import ctypes.wintypes as wintypes
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal

from .models import KeyEvent

logger = logging.getLogger(__name__)

# Win32 constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012

# Low-level keyboard proc signature
if sys.platform == "win32":
    HOOKPROC = ctypes.WINFUNCTYPE(
        wintypes.LPARAM,   # LRESULT (pointer-sized)
        ctypes.c_int,      # nCode
        wintypes.WPARAM,   # wParam (pointer-sized)
        wintypes.LPARAM,   # lParam (pointer-sized)
    )


class _KeyboardHookThread(QThread):
    """Runs a Win32 message loop with a low-level keyboard hook."""

    def __init__(self, start_ms: float = 0.0,
                 events_list: List[KeyEvent] | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread_id: int = 0
        self._hook = None
        self._start_ms = start_ms
        # Direct append list — avoids cross-thread signal queuing losses
        self._events_list: List[KeyEvent] = events_list if events_list is not None else []
        # prevent GC of the callback
        self._proc = None

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
        events_list = self._events_list

        def low_level_handler(n_code, w_param, l_param):
            try:
                if n_code >= 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    ts = time.time() * 1000 - start_ms
                    events_list.append(KeyEvent(timestamp=ts))
            except Exception:
                logger.exception("Error in keyboard hook callback")
            return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

        self._proc = HOOKPROC(low_level_handler)
        self._hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._proc, None, 0
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


class KeyboardTracker(QObject):
    """Records timestamps of key-down events during a recording session."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: Optional[_KeyboardHookThread] = None
        self._events: List[KeyEvent] = []
        self._start_time: float = 0.0

    def start(self, start_ms: float = 0.0) -> None:
        """Begin tracking keyboard events.

        *start_ms* — shared epoch (``time.time() * 1000``) so all trackers
        use the same time base.
        """
        if sys.platform != "win32":
            return
        self._events.clear()
        self._start_time = start_ms if start_ms > 0 else time.time() * 1000
        self._thread = _KeyboardHookThread(
            start_ms=self._start_time,
            events_list=self._events,
            parent=self,
        )
        self._thread.start()

    def stop(self) -> List[KeyEvent]:
        """Stop tracking and return collected events."""
        if self._thread is not None:
            self._thread.request_stop()
            self._thread.wait(2000)
            self._thread = None
        result = list(self._events)
        self._events.clear()
        return result

    @property
    def events(self) -> List[KeyEvent]:
        return list(self._events)
