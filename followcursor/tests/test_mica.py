"""Tests for mica.py — Windows 11 Mica/Acrylic backdrop effects."""

from app.mica import (
    is_mica_supported,
    is_acrylic_supported,
    enable_mica,
    enable_acrylic,
    disable_backdrop,
    _get_build_number,
)
import sys


def test_mica_module_imports():
    """mica.py imports cleanly."""
    pass  # Import above is the test


def test_get_build_number_returns_int():
    """_get_build_number returns an integer."""
    result = _get_build_number()
    assert isinstance(result, int)
    assert result >= 0


def test_is_mica_supported_returns_bool():
    """is_mica_supported returns a boolean."""
    result = is_mica_supported()
    assert isinstance(result, bool)


def test_is_acrylic_supported_returns_bool():
    """is_acrylic_supported returns a boolean."""
    result = is_acrylic_supported()
    assert isinstance(result, bool)


def test_enable_mica_returns_false_on_non_windows():
    """enable_mica returns False on non-Windows platforms."""
    if sys.platform != "win32":
        result = enable_mica(0)
        assert result is False


def test_enable_acrylic_returns_false_on_non_windows():
    """enable_acrylic returns False on non-Windows platforms."""
    if sys.platform != "win32":
        result = enable_acrylic(0)
        assert result is False


def test_disable_backdrop_returns_false_on_non_windows():
    """disable_backdrop returns False on non-Windows platforms."""
    if sys.platform != "win32":
        result = disable_backdrop(0)
        assert result is False


def test_enable_mica_with_invalid_hwnd_does_not_crash():
    """enable_mica with invalid hwnd should not raise, just return False."""
    try:
        result = enable_mica(0)
        # On Windows with unsupported build, should return False gracefully
        # On non-Windows, should also return False
        assert isinstance(result, bool)
    except Exception as e:
        assert False, f"enable_mica raised: {e}"


def test_enable_acrylic_with_invalid_hwnd_does_not_crash():
    """enable_acrylic with invalid hwnd should not raise, just return False."""
    try:
        result = enable_acrylic(0)
        assert isinstance(result, bool)
    except Exception as e:
        assert False, f"enable_acrylic raised: {e}"


def test_disable_backdrop_with_invalid_hwnd_does_not_crash():
    """disable_backdrop with invalid hwnd should not raise, just return False."""
    try:
        result = disable_backdrop(0)
        assert isinstance(result, bool)
    except Exception as e:
        assert False, f"disable_backdrop raised: {e}"
