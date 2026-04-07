"""Tests for Win32 hook struct layouts in click_tracker and keyboard_tracker.

Verifies that dwExtraInfo is declared as a pointer-sized type (c_void_p) so
that KBDLLHOOKSTRUCT and MSLLHOOKSTRUCT match the Win32 ABI on both 32-bit and
64-bit platforms.

Also verifies that modifier VK codes (Ctrl, Alt, Win) are NOT in _IGNORE_VKS
so the keystroke overlay's "Modifiers Only" and "Shortcuts Only" modes work.
"""

import ctypes
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Win32-only structs")
class TestKBDLLHOOKSTRUCT:
    def test_dwExtraInfo_is_pointer_sized(self) -> None:
        pytest.importorskip("PySide6")
        from app.keyboard_tracker import KBDLLHOOKSTRUCT

        field_map = {name: ftype for name, ftype in KBDLLHOOKSTRUCT._fields_}
        assert field_map["dwExtraInfo"] is ctypes.c_void_p, (
            "dwExtraInfo must be ctypes.c_void_p (ULONG_PTR), "
            f"got {field_map['dwExtraInfo']!r}"
        )

    def test_struct_size_matches_win32(self) -> None:
        pytest.importorskip("PySide6")
        from app.keyboard_tracker import KBDLLHOOKSTRUCT

        # KBDLLHOOKSTRUCT: vkCode(4) + scanCode(4) + flags(4) + time(4) + dwExtraInfo(ptr)
        expected = 4 * 4 + ctypes.sizeof(ctypes.c_void_p)
        assert ctypes.sizeof(KBDLLHOOKSTRUCT) == expected, (
            f"KBDLLHOOKSTRUCT size {ctypes.sizeof(KBDLLHOOKSTRUCT)} != {expected}"
        )


class TestIgnoreVKs:
    """Verify _IGNORE_VKS does not contain modifier VK codes.

    Ctrl, Alt, and Win modifier VKs must be recorded so that the keystroke
    overlay's "Modifiers Only" and "Shortcuts Only" filter modes can detect
    modifier state.  (Shift is still filtered because it is not a shortcut
    modifier in the renderer's MODIFIER_VKS definition.)
    """

    # All Ctrl/Alt/Win VK codes that must NOT be filtered
    REQUIRED_MODIFIER_VKS = (
        0x11,        # Ctrl (generic)
        0x12,        # Alt (generic)
        0xA2, 0xA3,  # LCtrl, RCtrl
        0xA4, 0xA5,  # LAlt, RAlt
        0x5B, 0x5C,  # LWin, RWin
    )

    def test_ctrl_alt_win_not_in_ignore_vks(self) -> None:
        pytest.importorskip("PySide6")
        from app.keyboard_tracker import _IGNORE_VKS

        for vk in self.REQUIRED_MODIFIER_VKS:
            assert vk not in _IGNORE_VKS, (
                f"Modifier VK 0x{vk:02X} must not be in _IGNORE_VKS — "
                "it is needed by the keystroke overlay filter modes"
            )


@pytest.mark.skipif(sys.platform != "win32", reason="Win32-only structs")
class TestMSLLHOOKSTRUCT:
    def test_dwExtraInfo_is_pointer_sized(self) -> None:
        pytest.importorskip("PySide6")
        from app.click_tracker import MSLLHOOKSTRUCT

        field_map = {name: ftype for name, ftype in MSLLHOOKSTRUCT._fields_}
        assert field_map["dwExtraInfo"] is ctypes.c_void_p, (
            "dwExtraInfo must be ctypes.c_void_p (ULONG_PTR), "
            f"got {field_map['dwExtraInfo']!r}"
        )

    def test_struct_size_matches_win32(self) -> None:
        pytest.importorskip("PySide6")
        from app.click_tracker import MSLLHOOKSTRUCT

        # Use the actual field offset to account for any alignment padding inserted
        # by ctypes between the last DWORD field and the pointer-sized dwExtraInfo.
        expected = MSLLHOOKSTRUCT.dwExtraInfo.offset + ctypes.sizeof(ctypes.c_void_p)
        assert ctypes.sizeof(MSLLHOOKSTRUCT) == expected, (
            f"MSLLHOOKSTRUCT size {ctypes.sizeof(MSLLHOOKSTRUCT)} != {expected}"
        )
