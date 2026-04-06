"""Tests for Win32 hook struct layouts in click_tracker and keyboard_tracker.

Verifies that dwExtraInfo is declared as a pointer-sized type (c_void_p) so
that KBDLLHOOKSTRUCT and MSLLHOOKSTRUCT match the Win32 ABI on both 32-bit and
64-bit platforms.
"""

import ctypes
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Win32-only structs")
class TestKBDLLHOOKSTRUCT:
    def test_dwExtraInfo_is_pointer_sized(self) -> None:
        from app.keyboard_tracker import KBDLLHOOKSTRUCT

        field_map = {name: ftype for name, ftype in KBDLLHOOKSTRUCT._fields_}
        assert field_map["dwExtraInfo"] is ctypes.c_void_p, (
            "dwExtraInfo must be ctypes.c_void_p (ULONG_PTR), "
            f"got {field_map['dwExtraInfo']!r}"
        )

    def test_struct_size_matches_win32(self) -> None:
        from app.keyboard_tracker import KBDLLHOOKSTRUCT

        # KBDLLHOOKSTRUCT: vkCode(4) + scanCode(4) + flags(4) + time(4) + dwExtraInfo(ptr)
        expected = 4 * 4 + ctypes.sizeof(ctypes.c_void_p)
        assert ctypes.sizeof(KBDLLHOOKSTRUCT) == expected, (
            f"KBDLLHOOKSTRUCT size {ctypes.sizeof(KBDLLHOOKSTRUCT)} != {expected}"
        )


@pytest.mark.skipif(sys.platform != "win32", reason="Win32-only structs")
class TestMSLLHOOKSTRUCT:
    def test_dwExtraInfo_is_pointer_sized(self) -> None:
        from app.click_tracker import MSLLHOOKSTRUCT

        field_map = {name: ftype for name, ftype in MSLLHOOKSTRUCT._fields_}
        assert field_map["dwExtraInfo"] is ctypes.c_void_p, (
            "dwExtraInfo must be ctypes.c_void_p (ULONG_PTR), "
            f"got {field_map['dwExtraInfo']!r}"
        )

    def test_struct_size_matches_win32(self) -> None:
        from app.click_tracker import MSLLHOOKSTRUCT

        # Use the actual field offset to account for any alignment padding inserted
        # by ctypes between the last DWORD field and the pointer-sized dwExtraInfo.
        expected = MSLLHOOKSTRUCT.dwExtraInfo.offset + ctypes.sizeof(ctypes.c_void_p)
        assert ctypes.sizeof(MSLLHOOKSTRUCT) == expected, (
            f"MSLLHOOKSTRUCT size {ctypes.sizeof(MSLLHOOKSTRUCT)} != {expected}"
        )
