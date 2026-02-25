"""Windows window enumeration utilities using ctypes."""

import ctypes
from ctypes import wintypes
from typing import List, Optional

import numpy as np

user32 = ctypes.windll.user32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
DWMWA_CLOAKED = 14


def _is_alt_tab_window(hwnd: int) -> bool:
    """Check if a window would appear in Alt-Tab (taskbar)."""
    if not user32.IsWindowVisible(hwnd):
        return False
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return False
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if ex_style & WS_EX_TOOLWINDOW:
        return False
    if ex_style & WS_EX_NOACTIVATE:
        return False
    # Check if cloaked (UWP background apps)
    try:
        cloaked = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
        if cloaked.value:
            return False
    except Exception:
        pass
    return True


def enumerate_windows(exclude_hwnd: int = 0) -> List[dict]:
    """Return a list of visible, alt-tab-eligible windows.

    Args:
        exclude_hwnd: Window handle to exclude (e.g. our own app window).
    """
    windows: List[dict] = []

    def callback(hwnd, lparam):
        if hwnd == exclude_hwnd:
            return True
        if not _is_alt_tab_window(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w < 100 or h < 50:
            return True
        display_name = title if len(title) <= 45 else title[:42] + "\u2026"
        windows.append({
            "type": "window",
            "hwnd": hwnd,
            "title": title,
            "name": display_name,
            "left": rect.left,
            "top": rect.top,
            "width": w,
            "height": h,
        })
        return True

    cb = WNDENUMPROC(callback)
    user32.EnumWindows(cb, 0)
    return windows


def get_window_rect(hwnd: int) -> Optional[dict]:
    """Get the current rect of a window. Returns None if window is gone."""
    try:
        if not user32.IsWindow(hwnd):
            return None
        # Use DWM extended frame bounds for accurate rect on high-DPI
        rect = wintypes.RECT()
        try:
            DWMWA_EXTENDED_FRAME_BOUNDS = 9
            hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
                ctypes.byref(rect), ctypes.sizeof(rect),
            )
            if hr != 0:
                raise OSError
        except Exception:
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return {
            "left": rect.left,
            "top": rect.top,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top,
        }
    except Exception:
        return None


def capture_window_thumbnail(
    hwnd: int, max_w: int = 400, max_h: int = 220,
) -> Optional[np.ndarray]:
    """Capture a thumbnail of a window using Win32 PrintWindow.

    Uses the window's own device context so overlapping windows don't bleed through.
    Qt sets PER_MONITOR_DPI_AWARE_V2, so GetWindowRect already returns physical pixels.
    Returns an RGB numpy array sized to fit within (max_w, max_h), or None.
    """
    import cv2

    rect = get_window_rect(hwnd)
    if not rect or rect["width"] < 10 or rect["height"] < 10:
        return None

    # Use GetWindowRect — already physical pixels under Qt's DPI awareness
    raw_rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(raw_rect))
    w = raw_rect.right - raw_rect.left
    h = raw_rect.bottom - raw_rect.top
    if w < 10 or h < 10:
        return None

    try:
        gdi32 = ctypes.windll.gdi32

        hwnd_dc = user32.GetWindowDC(hwnd)
        if not hwnd_dc:
            return None

        mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
        bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
        old_bmp = gdi32.SelectObject(mem_dc, bitmap)

        # PW_RENDERFULLCONTENT = 2 (works for DWM-composed windows)
        result = user32.PrintWindow(hwnd, mem_dc, 2)
        if not result:
            result = user32.PrintWindow(hwnd, mem_dc, 0)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32),
                ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # top-down
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0  # BI_RGB

        buf = (ctypes.c_char * (w * h * 4))()
        gdi32.GetDIBits(mem_dc, bitmap, 0, h, buf, ctypes.byref(bmi), 0)

        gdi32.SelectObject(mem_dc, old_bmp)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, hwnd_dc)

        frame = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)
        if frame.max() == 0:
            return _capture_window_mss_fallback(hwnd, rect["width"], rect["height"], max_w, max_h)

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        scale = min(max_w / w, max_h / h)
        thumb = cv2.resize(frame_rgb, (int(w * scale), int(h * scale)),
                           interpolation=cv2.INTER_AREA)
        return thumb

    except Exception:
        return _capture_window_mss_fallback(hwnd, rect["width"], rect["height"], max_w, max_h)


def _capture_window_mss_fallback(
    hwnd: int, w: int, h: int, max_w: int, max_h: int,
) -> Optional[np.ndarray]:
    """Fallback: grab the screen region where the window sits."""
    import cv2
    import mss as mss_mod

    rect = get_window_rect(hwnd)
    if not rect:
        return None
    try:
        with mss_mod.mss() as sct:
            monitor = {
                "left": rect["left"],
                "top": rect["top"],
                "width": rect["width"],
                "height": rect["height"],
            }
            img = sct.grab(monitor)
            frame = np.array(img)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
            scale = min(max_w / w, max_h / h)
            thumb = cv2.resize(frame_rgb, (int(w * scale), int(h * scale)))
            return thumb
    except Exception:
        return None
