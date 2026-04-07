"""Windows 11 Mica/Acrylic backdrop effects via DWM API.

Mica is a material that samples the desktop wallpaper to create a personalized,
context-aware background. Acrylic provides real-time blur of content behind the
window. Both are part of Windows 11 Fluent 2 design system.

Reference: https://learn.microsoft.com/en-us/windows/apps/design/style/mica
"""

import sys
import ctypes
import logging

logger = logging.getLogger(__name__)

# DWM Window Attributes
DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # Windows 10 Build 19041+
DWMWA_SYSTEMBACKDROP_TYPE = 38      # Windows 11 Build 22621+
DWMWA_MICA_EFFECT = 1029            # Older Windows 11 builds (fallback)

# System Backdrop Types
DWM_SYSTEMBACKDROP_AUTO = 0
DWM_SYSTEMBACKDROP_NONE = 1
DWM_SYSTEMBACKDROP_MICA = 2
DWM_SYSTEMBACKDROP_ACRYLIC = 3
DWM_SYSTEMBACKDROP_TABBED = 4


def _get_build_number() -> int:
    """Get Windows build number. Returns 0 on non-Windows."""
    if sys.platform != "win32":
        return 0
    try:
        ver = sys.getwindowsversion()
        return ver.build
    except Exception:
        return 0


def is_mica_supported() -> bool:
    """Returns True on Windows 11 Build 22621+."""
    return _get_build_number() >= 22621


def is_acrylic_supported() -> bool:
    """Returns True on Windows 11 Build 22621+ (same requirement as Mica)."""
    return is_mica_supported()


def _set_dwm_attribute(hwnd: int, attribute: int, value: int) -> bool:
    """Set a DWM window attribute. Returns True on success (S_OK)."""
    if sys.platform != "win32":
        return False
    try:
        dwmapi = ctypes.windll.dwmapi
        dwm_set_window_attribute = dwmapi.DwmSetWindowAttribute
        dwm_set_window_attribute.argtypes = (
            ctypes.c_void_p,   # hwnd
            ctypes.c_uint32,   # attribute
            ctypes.c_void_p,   # pvAttribute
            ctypes.c_uint32,   # cbAttribute
        )
        dwm_set_window_attribute.restype = ctypes.c_long

        hwnd_ptr = ctypes.c_void_p(hwnd)
        val = ctypes.c_int(value)
        result = dwm_set_window_attribute(
            hwnd_ptr,
            ctypes.c_uint32(attribute),
            ctypes.cast(ctypes.byref(val), ctypes.c_void_p),
            ctypes.c_uint32(ctypes.sizeof(val)),
        )
        return result == 0  # S_OK
    except Exception as e:
        logger.debug(f"DwmSetWindowAttribute({attribute}, {value}) failed: {e}")
        return False


def enable_mica(hwnd: int, dark_mode: bool = True) -> bool:
    """Enable Mica backdrop. Requires Windows 11 Build 22621+.
    
    Args:
        hwnd: Window handle (from QWidget.winId())
        dark_mode: True for dark title bar, False for light
        
    Returns:
        True if Mica was successfully enabled, False otherwise.
    """
    if not is_mica_supported():
        logger.debug("Mica not supported on this Windows version")
        return False
    
    # Set dark/light title bar
    _set_dwm_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark_mode else 0)
    
    # Enable Mica backdrop
    success = _set_dwm_attribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWM_SYSTEMBACKDROP_MICA)
    
    if success:
        logger.debug("Mica backdrop enabled")
    else:
        logger.debug("Failed to enable Mica backdrop")
    
    return success


def enable_acrylic(hwnd: int, dark_mode: bool = True) -> bool:
    """Enable Acrylic backdrop. Requires Windows 11 Build 22621+.
    
    Args:
        hwnd: Window handle (from QWidget.winId())
        dark_mode: True for dark title bar, False for light
        
    Returns:
        True if Acrylic was successfully enabled, False otherwise.
    """
    if not is_mica_supported():
        logger.debug("Acrylic not supported on this Windows version")
        return False
    
    # Set dark/light title bar
    _set_dwm_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark_mode else 0)
    
    # Enable Acrylic backdrop
    success = _set_dwm_attribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWM_SYSTEMBACKDROP_ACRYLIC)
    
    if success:
        logger.debug("Acrylic backdrop enabled")
    else:
        logger.debug("Failed to enable Acrylic backdrop")
    
    return success


def disable_backdrop(hwnd: int) -> bool:
    """Remove any backdrop effect. Returns window to default solid background.
    
    Args:
        hwnd: Window handle (from QWidget.winId())
        
    Returns:
        True if backdrop was successfully disabled, False otherwise.
    """
    return _set_dwm_attribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, DWM_SYSTEMBACKDROP_NONE)
