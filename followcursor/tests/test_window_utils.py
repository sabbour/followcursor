"""Tests for app.window_utils — capture dimension scaling and GDI handle cleanup."""

import sys
import ctypes
from unittest.mock import MagicMock, patch

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


# Sentinel used to short-circuit capture after CreateCompatibleBitmap records
# its arguments, without allocating a large pixel buffer.
class _DimsCaptured(Exception):
    pass


# ── Capture dimension scaling ────────────────────────────────────────


class TestCaptureDimensionScale:
    """Verify that the GDI bitmap is created at thumbnail-bounded size."""

    def _run_capture(self, raw_w: int, raw_h: int, max_w: int = 400, max_h: int = 220):
        """Return (cap_w, cap_h) that were passed to CreateCompatibleBitmap."""
        import app.window_utils as wu

        captured_dims: dict = {}

        def fake_get_window_rect(hwnd, ref):
            r = ref._obj
            r.right = raw_w
            r.left = 0
            r.bottom = raw_h
            r.top = 0

        def fake_create_compatible_bitmap(dc, w, h):
            captured_dims["w"] = w
            captured_dims["h"] = h
            # Raise immediately to avoid allocating a large pixel buffer; the
            # outer except in capture_window_thumbnail will call the fallback.
            raise _DimsCaptured("short-circuit after dimension capture")

        mock_gdi32 = MagicMock()
        mock_gdi32.CreateCompatibleDC.return_value = 2
        mock_gdi32.CreateCompatibleBitmap.side_effect = fake_create_compatible_bitmap

        mock_user32 = MagicMock()
        mock_user32.GetWindowDC.return_value = 1
        mock_user32.GetWindowRect.side_effect = fake_get_window_rect

        with (
            patch.object(wu, "user32", mock_user32),
            patch("ctypes.windll") as mock_windll,
            patch.object(wu, "get_window_rect", return_value={"left": 0, "top": 0, "width": raw_w, "height": raw_h}),
            patch.object(wu, "_capture_window_mss_fallback", return_value=None),
        ):
            mock_windll.gdi32 = mock_gdi32
            result = wu.capture_window_thumbnail(12345, max_w=max_w, max_h=max_h)

        assert result is None  # fallback was called
        return captured_dims

    def test_small_window_uses_original_dimensions(self) -> None:
        """A window smaller than max size should not be upscaled."""
        dims = self._run_capture(200, 100, max_w=400, max_h=220)
        assert dims.get("w") == 200
        assert dims.get("h") == 100

    def test_wide_window_scaled_to_fit_width(self) -> None:
        """Bitmap width must not exceed max_w for a very wide window."""
        dims = self._run_capture(10000, 1080, max_w=400, max_h=220)
        assert dims.get("w") is not None
        assert dims["w"] <= 400
        assert dims["h"] <= 220

    def test_tall_window_scaled_to_fit_height(self) -> None:
        """Bitmap height must not exceed max_h for a very tall window."""
        dims = self._run_capture(1920, 9000, max_w=400, max_h=220)
        assert dims.get("h") is not None
        assert dims["w"] <= 400
        assert dims["h"] <= 220

    def test_large_window_always_bounded_by_thumbnail_size(self) -> None:
        """Any window larger than max size produces a bitmap ≤ max_w × max_h."""
        dims = self._run_capture(16384, 16384, max_w=400, max_h=220)
        assert dims.get("w") is not None
        assert dims["w"] <= 400
        assert dims["h"] <= 220

    def test_aspect_ratio_preserved(self) -> None:
        """Scaling must preserve the aspect ratio (within 1 pixel rounding)."""
        dims = self._run_capture(1920, 1080, max_w=400, max_h=220)
        w, h = dims["w"], dims["h"]
        original_ratio = 1920 / 1080
        captured_ratio = w / h
        assert abs(original_ratio - captured_ratio) < 0.05


# ── GDI handle cleanup ───────────────────────────────────────────────


class TestGdiHandleCleanup:
    """Verify GDI handles are released on every exit path."""

    def _make_cleanup_mocks(self, raw_w: int, raw_h: int):
        """Return (mock_gdi32, mock_user32, cleanup_calls) wired to record cleanup."""
        cleanup_calls: list = []

        def fake_get_window_rect(hwnd, ref):
            r = ref._obj
            r.right = raw_w
            r.left = 0
            r.bottom = raw_h
            r.top = 0

        mock_gdi32 = MagicMock()
        mock_gdi32.CreateCompatibleDC.return_value = 10
        mock_gdi32.CreateCompatibleBitmap.return_value = 20
        mock_gdi32.SelectObject.return_value = 30
        mock_gdi32.DeleteObject.side_effect = lambda obj: cleanup_calls.append(("DeleteObject", obj))
        mock_gdi32.DeleteDC.side_effect = lambda dc: cleanup_calls.append(("DeleteDC", dc))

        mock_user32 = MagicMock()
        mock_user32.GetWindowDC.return_value = 5
        mock_user32.GetWindowRect.side_effect = fake_get_window_rect
        mock_user32.PrintWindow.return_value = 1
        mock_user32.ReleaseDC.side_effect = lambda hwnd, dc: cleanup_calls.append(("ReleaseDC", dc))

        return mock_gdi32, mock_user32, cleanup_calls

    def test_gdi_handles_released_on_getdibits_exception(self) -> None:
        """DeleteDC, DeleteObject, and ReleaseDC must be called when GetDIBits raises."""
        import app.window_utils as wu

        W, H = 200, 100
        mock_gdi32, mock_user32, cleanup_calls = self._make_cleanup_mocks(W, H)
        mock_gdi32.GetDIBits.side_effect = RuntimeError("simulated GDI failure")

        with (
            patch.object(wu, "user32", mock_user32),
            patch("ctypes.windll") as mock_windll,
            patch.object(wu, "get_window_rect", return_value={"left": 0, "top": 0, "width": W, "height": H}),
            patch.object(wu, "_capture_window_mss_fallback", return_value=None),
        ):
            mock_windll.gdi32 = mock_gdi32
            result = wu.capture_window_thumbnail(99999)

        assert result is None  # fallback returned, exception did not propagate
        call_names = [name for name, _ in cleanup_calls]
        assert "DeleteObject" in call_names, "DeleteObject (bitmap) must be called on exception"
        assert "DeleteDC" in call_names, "DeleteDC (mem_dc) must be called on exception"
        assert "ReleaseDC" in call_names, "ReleaseDC (hwnd_dc) must be called on exception"

    def test_gdi_handles_released_on_early_allocation_failure(self) -> None:
        """hwnd_dc and mem_dc must be cleaned up when CreateCompatibleBitmap fails."""
        import app.window_utils as wu

        W, H = 200, 100
        mock_gdi32, mock_user32, cleanup_calls = self._make_cleanup_mocks(W, H)
        mock_gdi32.CreateCompatibleBitmap.side_effect = RuntimeError("allocation failed")
        # bitmap and old_bmp were never acquired, so only mem_dc and hwnd_dc need cleanup.

        with (
            patch.object(wu, "user32", mock_user32),
            patch("ctypes.windll") as mock_windll,
            patch.object(wu, "get_window_rect", return_value={"left": 0, "top": 0, "width": W, "height": H}),
            patch.object(wu, "_capture_window_mss_fallback", return_value=None),
        ):
            mock_windll.gdi32 = mock_gdi32
            result = wu.capture_window_thumbnail(99999)

        assert result is None
        call_names = [name for name, _ in cleanup_calls]
        assert "DeleteDC" in call_names, "DeleteDC (mem_dc) must be called even on early failure"
        assert "ReleaseDC" in call_names, "ReleaseDC (hwnd_dc) must be called even on early failure"
        # bitmap was never created, so DeleteObject should NOT be called for it
        assert "DeleteObject" not in call_names, "DeleteObject must not be called when bitmap was never created"

    def test_gdi_handles_released_on_success(self) -> None:
        """DeleteDC, DeleteObject, and ReleaseDC must also be called on the success path."""
        import app.window_utils as wu

        W, H = 100, 50
        mock_gdi32, mock_user32, cleanup_calls = self._make_cleanup_mocks(W, H)

        def fake_get_dibits(mem_dc, bitmap, start, lines, buf, bmi_ref, usage):
            # Write non-zero pixel data so frame.max() != 0 → not blank
            ctypes.memmove(buf, b"\xff" * (W * H * 4), W * H * 4)
            return 1

        mock_gdi32.GetDIBits.side_effect = fake_get_dibits

        with (
            patch.object(wu, "user32", mock_user32),
            patch("ctypes.windll") as mock_windll,
            patch.object(wu, "get_window_rect", return_value={"left": 0, "top": 0, "width": W, "height": H}),
        ):
            mock_windll.gdi32 = mock_gdi32
            wu.capture_window_thumbnail(99999)

        call_names = [name for name, _ in cleanup_calls]
        assert "DeleteObject" in call_names, "DeleteObject must be called on success path"
        assert "DeleteDC" in call_names, "DeleteDC must be called on success path"
        assert "ReleaseDC" in call_names, "ReleaseDC must be called on success path"

