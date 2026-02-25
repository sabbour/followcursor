"""Generate the FollowCursor app icon at runtime using QPainter.

Also writes an .ico file on first run so Windows taskbar picks it up.
"""

import os
import struct
from typing import List, Tuple

from PySide6.QtCore import Qt, QPointF, QBuffer, QIODevice
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)


_ICO_CACHE: str | None = None


def create_app_icon() -> QIcon:
    """Return a multi-size QIcon for the application.

    On Windows the icon is also saved as an .ico file next to main.py
    so that SetCurrentProcessExplicitAppUserModelID can find it.
    """
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_render(size))
    return icon


def get_ico_path() -> str:
    """Return path to a generated .ico file (created on first call)."""
    global _ICO_CACHE
    if _ICO_CACHE and os.path.isfile(_ICO_CACHE):
        return _ICO_CACHE

    ico_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "followcursor.ico")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images: List[Tuple[int, bytes]] = []

    for sz in sizes:
        pm = _render(sz)
        img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        images.append((sz, bytes(buf.data())))

    _write_ico(ico_path, images)
    _ICO_CACHE = ico_path
    return ico_path


def _write_ico(path: str, images: List[Tuple[int, bytes]]) -> None:
    """Write a multi-resolution .ico file using PNG-compressed entries."""
    n = len(images)
    header = struct.pack("<HHH", 0, 1, n)
    dir_entries = bytearray()
    data_blobs = bytearray()
    offset = 6 + n * 16

    for size, png_data in images:
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        entry = struct.pack(
            "<BBBBHHII",
            w, h, 0, 0, 1, 32, len(png_data), offset,
        )
        dir_entries += entry
        data_blobs += png_data
        offset += len(png_data)

    with open(path, "wb") as f:
        f.write(header)
        f.write(dir_entries)
        f.write(data_blobs)


def _render(size: int) -> QPixmap:
    """Paint the app icon at the given pixel size and return a QPixmap."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = size  # shorthand
    cx, cy = s / 2, s / 2

    # ── background circle with gradient ──────────────────────────
    bg_grad = QLinearGradient(0, 0, s, s)
    bg_grad.setColorAt(0.0, QColor("#7c3aed"))   # purple-600
    bg_grad.setColorAt(1.0, QColor("#4f46e5"))   # indigo-600
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bg_grad)
    r = s * 0.46
    p.drawEllipse(QPointF(cx, cy), r, r)

    # ── subtle glow ring ─────────────────────────────────────────
    glow = QRadialGradient(QPointF(cx, cy), r * 1.15)
    glow.setColorAt(0.75, QColor(139, 92, 246, 0))
    glow.setColorAt(1.0, QColor(139, 92, 246, 60))
    p.setBrush(glow)
    p.drawEllipse(QPointF(cx, cy), r * 1.15, r * 1.15)

    # ── cursor arrow (white) ─────────────────────────────────────
    # Draw a classic pointer cursor, offset to upper-left of center
    cursor_x = cx - s * 0.12
    cursor_y = cy - s * 0.16
    cs = s * 0.38  # cursor height

    path = QPainterPath()
    path.moveTo(cursor_x, cursor_y)                          # tip
    path.lineTo(cursor_x, cursor_y + cs)                     # down
    path.lineTo(cursor_x + cs * 0.28, cursor_y + cs * 0.72) # notch right
    path.lineTo(cursor_x + cs * 0.45, cursor_y + cs * 1.0)  # lower-right arm
    path.lineTo(cursor_x + cs * 0.55, cursor_y + cs * 0.88) # arm tip
    path.lineTo(cursor_x + cs * 0.35, cursor_y + cs * 0.62) # notch inner
    path.lineTo(cursor_x + cs * 0.65, cursor_y + cs * 0.62) # right wing
    path.closeSubpath()

    # dark outline
    p.setPen(QPen(QColor(0, 0, 0, 140), max(s * 0.03, 1)))
    p.setBrush(QColor("#ffffff"))
    p.drawPath(path)

    # ── small crosshair / focus dot at lower-right ───────────────
    fx = cx + s * 0.16
    fy = cy + s * 0.18
    dot_r = s * 0.06

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#facc15"))  # yellow-400 focus dot
    p.drawEllipse(QPointF(fx, fy), dot_r, dot_r)

    # crosshair lines
    pen = QPen(QColor("#facc15"), max(s * 0.02, 0.8))
    p.setPen(pen)
    line_len = s * 0.08
    p.drawLine(QPointF(fx - line_len, fy), QPointF(fx - dot_r * 1.6, fy))
    p.drawLine(QPointF(fx + dot_r * 1.6, fy), QPointF(fx + line_len, fy))
    p.drawLine(QPointF(fx, fy - line_len), QPointF(fx, fy - dot_r * 1.6))
    p.drawLine(QPointF(fx, fy + dot_r * 1.6), QPointF(fx, fy + line_len))

    p.end()
    return pm
