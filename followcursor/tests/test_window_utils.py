"""Tests for app.window_utils — dimension capping and GDI handle cleanup."""

import sys
import ctypes
from unittest.mock import MagicMock, patch

import pytest

# cv2 and ctypes.windll/WINFUNCTYPE are Windows/optional dependencies.  Mock
# them at the sys.modules / ctypes level *before* importing app.window_utils so
# the module-level initialisations don't blow up on non-Windows CI runners.
if "cv2" not in sys.modules:
    sys.modules["cv2"] = MagicMock()  # type: ignore[assignment]
if not hasattr(ctypes, "windll"):
    ctypes.windll = MagicMock()  # type: ignore[attr-defined]
    ctypes.windll.user32 = MagicMock()
if not hasattr(ctypes, "WINFUNCTYPE"):
    ctypes.WINFUNCTYPE = MagicMock()  # type: ignore[attr-defined]


# ── Dimension capping ────────────────────────────────────────────────


class TestCaptureDimensionCap:
    """Verify that oversized window dimensions are capped before GDI allocation."""

    def _make_raw_rect(self, w: int, h: int):
        """Return a mock raw RECT with the given dimensions."""
        rect = MagicMock()
        rect.right = w
        rect.left = 0
        rect.bottom = h
        rect.top = 0
        return rect

    def _run_capture(self, raw_w: int, raw_h: int):
        """Run capture_window_thumbnail with mocked Win32 calls and collect args."""
        import app.window_utils as wu

        captured_dims = {}

        def fake_get_window_rect(hwnd, ref):
            r = ref._obj
            r.right = raw_w
            r.left = 0
            r.bottom = raw_h
            r.top = 0

        def fake_get_window_dc(hwnd):
            return 1  # non-zero = success

        def fake_create_compatible_dc(dc):
            return 2

        def fake_create_compatible_bitmap(dc, w, h):
            captured_dims["w"] = w
            captured_dims["h"] = h
            return 3

        def fake_select_object(dc, obj):
            return 4

        def fake_print_window(hwnd, dc, flags):
            return 1

        def fake_get_dibits(*args):
            return 1

        def fake_delete_object(obj):
            pass

        def fake_delete_dc(dc):
            pass

        def fake_release_dc(hwnd, dc):
            pass

        mock_gdi32 = MagicMock()
        mock_gdi32.CreateCompatibleDC.side_effect = fake_create_compatible_dc
        mock_gdi32.CreateCompatibleBitmap.side_effect = fake_create_compatible_bitmap
        mock_gdi32.SelectObject.side_effect = fake_select_object
        mock_gdi32.GetDIBits.side_effect = fake_get_dibits
        mock_gdi32.DeleteObject.side_effect = fake_delete_object
        mock_gdi32.DeleteDC.side_effect = fake_delete_dc

        mock_user32 = MagicMock()
        mock_user32.GetWindowDC.side_effect = fake_get_window_dc
        mock_user32.GetWindowRect.side_effect = fake_get_window_rect
        mock_user32.PrintWindow.side_effect = fake_print_window
        mock_user32.ReleaseDC.side_effect = fake_release_dc

        with (
            patch.object(wu, "user32", mock_user32),
            patch("ctypes.windll") as mock_windll,
            patch.object(wu, "get_window_rect", return_value={"left": 0, "top": 0, "width": raw_w, "height": raw_h}),
            patch.object(wu, "_capture_window_mss_fallback", return_value=None),
        ):
            mock_windll.gdi32 = mock_gdi32
            try:
                wu.capture_window_thumbnail(12345, max_w=400, max_h=220)
            except Exception:
                pass

        return captured_dims

    def test_normal_window_dimensions_unchanged(self) -> None:
        """A 1920×1080 window should be passed as-is to CreateCompatibleBitmap."""
        dims = self._run_capture(1920, 1080)
        assert dims.get("w") == 1920
        assert dims.get("h") == 1080

    def test_oversized_width_capped_at_8192(self) -> None:
        """A window wider than 8192px must be capped before bitmap creation."""
        dims = self._run_capture(10000, 1080)
        assert dims.get("w") == 8192
        assert dims.get("h") == 1080

    def test_oversized_height_capped_at_8192(self) -> None:
        """A window taller than 8192px must be capped before bitmap creation."""
        dims = self._run_capture(1920, 9000)
        assert dims.get("w") == 1920
        assert dims.get("h") == 8192

    def test_both_dimensions_oversized_capped(self) -> None:
        """Both width and height over 8192px must both be capped."""
        dims = self._run_capture(16384, 16384)
        assert dims.get("w") == 8192
        assert dims.get("h") == 8192

    def test_exact_max_dim_is_not_reduced(self) -> None:
        """Exactly 8192×8192 should not be reduced."""
        dims = self._run_capture(8192, 8192)
        assert dims.get("w") == 8192
        assert dims.get("h") == 8192


# ── GDI handle cleanup on exception path ────────────────────────────


class TestGdiHandleCleanup:
    """Verify GDI handles are released even when GetDIBits raises an exception."""

    def test_gdi_handles_released_on_exception(self) -> None:
        """DeleteDC, DeleteObject, and ReleaseDC must be called even if an exception occurs."""
        import app.window_utils as wu

        cleanup_calls = []

        def fake_get_window_rect_raw(hwnd, ref):
            r = ref._obj
            r.right = 200
            r.left = 0
            r.bottom = 100
            r.top = 0

        mock_gdi32 = MagicMock()
        mock_gdi32.CreateCompatibleDC.return_value = 10
        mock_gdi32.CreateCompatibleBitmap.return_value = 20
        mock_gdi32.SelectObject.return_value = 30
        mock_gdi32.PrintWindow.return_value = 1
        mock_gdi32.GetDIBits.side_effect = RuntimeError("simulated GDI failure")
        mock_gdi32.DeleteObject.side_effect = lambda obj: cleanup_calls.append(("DeleteObject", obj))
        mock_gdi32.DeleteDC.side_effect = lambda dc: cleanup_calls.append(("DeleteDC", dc))

        mock_user32 = MagicMock()
        mock_user32.GetWindowDC.return_value = 5
        mock_user32.GetWindowRect.side_effect = fake_get_window_rect_raw
        mock_user32.PrintWindow.return_value = 1
        mock_user32.ReleaseDC.side_effect = lambda hwnd, dc: cleanup_calls.append(("ReleaseDC", dc))

        with (
            patch.object(wu, "user32", mock_user32),
            patch("ctypes.windll") as mock_windll,
            patch.object(wu, "get_window_rect", return_value={"left": 0, "top": 0, "width": 200, "height": 100}),
            patch.object(wu, "_capture_window_mss_fallback", return_value=None),
        ):
            mock_windll.gdi32 = mock_gdi32
            result = wu.capture_window_thumbnail(99999)

        # The fallback should be returned (not an exception propagated)
        assert result is None

        # All three cleanup calls must be present
        call_names = [name for name, _ in cleanup_calls]
        assert "DeleteObject" in call_names, "DeleteObject (bitmap) must be called on exception"
        assert "DeleteDC" in call_names, "DeleteDC (mem_dc) must be called on exception"
        assert "ReleaseDC" in call_names, "ReleaseDC (hwnd_dc) must be called on exception"

    def test_gdi_handles_released_on_success(self) -> None:
        """DeleteDC, DeleteObject, and ReleaseDC must also be called on the success path."""
        import app.window_utils as wu
        import numpy as np

        cleanup_calls = []
        W, H = 100, 50

        def fake_get_window_rect_raw(hwnd, ref):
            r = ref._obj
            r.right = W
            r.left = 0
            r.bottom = H
            r.top = 0

        def fake_get_dibits(mem_dc, bitmap, start, lines, buf, bmi_ref, usage):
            # Write non-zero pixel data so frame.max() != 0
            ctypes.memmove(buf, b"\xff" * (W * H * 4), W * H * 4)
            return 1

        mock_gdi32 = MagicMock()
        mock_gdi32.CreateCompatibleDC.return_value = 10
        mock_gdi32.CreateCompatibleBitmap.return_value = 20
        mock_gdi32.SelectObject.return_value = 30
        mock_gdi32.GetDIBits.side_effect = fake_get_dibits
        mock_gdi32.DeleteObject.side_effect = lambda obj: cleanup_calls.append(("DeleteObject", obj))
        mock_gdi32.DeleteDC.side_effect = lambda dc: cleanup_calls.append(("DeleteDC", dc))

        mock_user32 = MagicMock()
        mock_user32.GetWindowDC.return_value = 5
        mock_user32.GetWindowRect.side_effect = fake_get_window_rect_raw
        mock_user32.PrintWindow.return_value = 1
        mock_user32.ReleaseDC.side_effect = lambda hwnd, dc: cleanup_calls.append(("ReleaseDC", dc))

        with (
            patch.object(wu, "user32", mock_user32),
            patch("ctypes.windll") as mock_windll,
            patch.object(wu, "get_window_rect", return_value={"left": 0, "top": 0, "width": W, "height": H}),
            patch("cv2.cvtColor", return_value=np.zeros((H, W, 3), dtype=np.uint8)),
            patch("cv2.resize", return_value=np.zeros((H, W, 3), dtype=np.uint8)),
        ):
            mock_windll.gdi32 = mock_gdi32
            wu.capture_window_thumbnail(99999)

        call_names = [name for name, _ in cleanup_calls]
        assert "DeleteObject" in call_names, "DeleteObject must be called on success path"
        assert "DeleteDC" in call_names, "DeleteDC must be called on success path"
        assert "ReleaseDC" in call_names, "ReleaseDC must be called on success path"
