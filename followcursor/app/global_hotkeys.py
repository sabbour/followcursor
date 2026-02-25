"""Windows global hotkeys via RegisterHotKey / GetMessage loop."""

import sys
import ctypes
import ctypes.wintypes as wintypes
from typing import Optional

from PySide6.QtCore import QThread, Signal, QObject

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
VK_R = 0x52           # R

HOTKEY_RECORD_TOGGLE = 3


class _HotkeyThread(QThread):
    """Runs a Win32 message loop that listens for registered hotkeys."""

    triggered = Signal(int)  # hotkey id

    def __init__(self, hotkeys: list, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread_id: int = 0
        self._hotkeys = hotkeys  # list of (id, modifiers, vk)

    def run(self) -> None:
        if sys.platform != "win32":
            return

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        self._thread_id = kernel32.GetCurrentThreadId()

        for hk_id, mods, vk in self._hotkeys:
            user32.RegisterHotKey(None, hk_id, mods, vk)

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                self.triggered.emit(msg.wParam)

        for hk_id, _mods, _vk in self._hotkeys:
            user32.UnregisterHotKey(None, hk_id)

    def request_stop(self) -> None:
        if self._thread_id and sys.platform == "win32":
            ctypes.windll.user32.PostThreadMessageW(  # type: ignore[attr-defined]
                self._thread_id, WM_QUIT, 0, 0
            )


class GlobalHotkeys(QObject):
    """Global hotkey: Ctrl+Shift+R toggles recording (always active)."""

    record_toggle_pressed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._record_thread: Optional[_HotkeyThread] = None

    # ── persistent record hotkey ────────────────────────────────────

    def register_record_hotkey(self) -> None:
        """Register Ctrl+Shift+R globally (call once at startup)."""
        if sys.platform != "win32" or self._record_thread is not None:
            return
        self._record_thread = _HotkeyThread(
            [(HOTKEY_RECORD_TOGGLE, MOD_CONTROL | MOD_SHIFT, VK_R)],
            self,
        )
        self._record_thread.triggered.connect(self._on_triggered)
        self._record_thread.start()

    def unregister_record_hotkey(self) -> None:
        if self._record_thread is not None:
            self._record_thread.request_stop()
            self._record_thread.wait(2000)
            self._record_thread = None

    # ── dispatch ────────────────────────────────────────────────────

    def _on_triggered(self, hotkey_id: int) -> None:
        if hotkey_id == HOTKEY_RECORD_TOGGLE:
            self.record_toggle_pressed.emit()
