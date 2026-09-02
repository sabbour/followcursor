"""Startup splash screen helpers for FollowCursor."""

from __future__ import annotations

from PySide6.QtCore import QSettings, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen, QWidget

from . import tokens as T


SPLASH_SIZE = QSize(480, 280)


def _scaled_pixmap(size: QSize) -> QPixmap:
    """Create a pixmap sized for the current screen scale factor."""
    dpr = 1.0
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        try:
            dpr = max(1.0, float(screen.devicePixelRatio()))
        except Exception:
            dpr = 1.0

    pixmap = QPixmap(int(size.width() * dpr), int(size.height() * dpr))
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def create_splash_pixmap(icon: QIcon, dark_mode: bool, version: str) -> QPixmap:
    """Render the startup splash artwork for the active theme."""
    pixmap = _scaled_pixmap(SPLASH_SIZE)
    pixmap.fill(QColor(T.bg_canvas(dark=dark_mode)))

    panel_color = QColor(T.bg_track(dark=dark_mode))
    panel_color = panel_color.lighter(108) if dark_mode else panel_color
    panel_border = QColor(T.bg_track_border(dark=dark_mode))
    scene_color = QColor(T.bg_canvas(dark=dark_mode))
    scene_layer = QColor(T.bg_track(dark=dark_mode))
    title_color = QColor(T.fg_primary(dark=dark_mode))
    body_color = QColor(T.fg_muted(dark=dark_mode))
    accent = QColor(T.BRAND if dark_mode else T.LIGHT_BRAND_BG)
    accent_alt = QColor(T.BRAND_ACTIVE if dark_mode else T.LIGHT_BRAND_BG_HOVER)
    accent_soft = QColor(accent)
    accent_soft.setAlpha(38 if dark_mode else 24)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    card_rect = QRectF(20, 20, SPLASH_SIZE.width() - 40, SPLASH_SIZE.height() - 40)
    card_path = QPainterPath()
    card_path.addRoundedRect(card_rect, T.RADIUS_XLARGE, T.RADIUS_XLARGE)

    card_gradient = QLinearGradient(card_rect.topLeft(), card_rect.bottomRight())
    card_gradient.setColorAt(0.0, panel_color)
    card_gradient.setColorAt(1.0, QColor(T.bg_canvas(dark=dark_mode)))
    painter.fillPath(card_path, card_gradient)
    painter.strokePath(card_path, QPen(panel_border, 1))

    painter.save()
    painter.setClipPath(card_path)
    accent_bar = QRectF(card_rect.left(), card_rect.top(), card_rect.width(), 5)
    accent_gradient = QLinearGradient(accent_bar.topLeft(), accent_bar.topRight())
    accent_gradient.setColorAt(0.0, accent_alt)
    accent_gradient.setColorAt(0.5, accent)
    accent_gradient.setColorAt(1.0, accent_alt)
    painter.fillRect(accent_bar, accent_gradient)
    painter.restore()

    scene_rect = QRectF(42, 54, 142, 132)
    scene_gradient = QLinearGradient(scene_rect.topLeft(), scene_rect.bottomRight())
    scene_gradient.setColorAt(0.0, scene_layer)
    scene_gradient.setColorAt(1.0, scene_color)
    painter.setPen(QPen(panel_border, 1))
    painter.setBrush(scene_gradient)
    painter.drawRoundedRect(scene_rect, T.RADIUS_LARGE, T.RADIUS_LARGE)

    mock_surface = QColor(panel_border)
    mock_surface.setAlpha(70 if dark_mode else 42)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(mock_surface)
    painter.drawRoundedRect(QRectF(54, 66, 118, 9), 4, 4)
    painter.drawRoundedRect(QRectF(54, 84, 47, 56), T.RADIUS_SMALL, T.RADIUS_SMALL)
    painter.drawRoundedRect(QRectF(108, 84, 64, 24), T.RADIUS_SMALL, T.RADIUS_SMALL)
    painter.drawRoundedRect(QRectF(108, 115, 64, 25), T.RADIUS_SMALL, T.RADIUS_SMALL)

    camera_path = QPainterPath()
    camera_path.moveTo(65, 158)
    camera_path.cubicTo(82, 153, 94, 143, 108, 128)
    camera_path.cubicTo(122, 112, 135, 102, 151, 94)
    path_pen = QPen(accent, 2)
    path_pen.setDashPattern([3, 3])
    painter.setPen(path_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(camera_path)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(accent)
    painter.drawEllipse(QRectF(61, 154, 8, 8))
    painter.drawEllipse(QRectF(104, 124, 8, 8))
    painter.setBrush(accent_soft)
    painter.drawEllipse(QRectF(119, 62, 64, 64))
    painter.setPen(QPen(accent, 2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(124, 67, 54, 54))
    painter.drawPixmap(127, 70, icon.pixmap(QSize(48, 48)))

    title_font = QFont("Segoe UI Variable")
    title_font.setPixelSize(T.FONT_SIZE_TITLE_3)
    title_font.setWeight(QFont.Weight(T.FONT_WEIGHT_SEMIBOLD))
    painter.setFont(title_font)
    painter.setPen(title_color)
    painter.drawText(
        QRectF(208, 57, 226, 38),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        "FollowCursor",
    )

    subtitle_font = QFont("Segoe UI Variable")
    subtitle_font.setPixelSize(T.FONT_SIZE_BODY_2)
    subtitle_font.setWeight(QFont.Weight(T.FONT_WEIGHT_REGULAR))
    painter.setFont(subtitle_font)
    painter.setPen(body_color)
    painter.drawText(
        QRectF(208, 101, 222, 62),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
        "Cinematic screen recording with cursor-following zoom",
    )

    separator = QColor(panel_border)
    separator.setAlpha(130 if dark_mode else 90)
    painter.setPen(QPen(separator, 1))
    painter.drawLine(42, 205, 438, 205)

    painter.setPen(QPen(accent, 2))
    painter.setBrush(accent_soft)
    painter.drawEllipse(QRectF(43, 220, 14, 14))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(accent)
    painter.drawEllipse(QRectF(48, 225, 4, 4))

    status_font = QFont("Segoe UI Variable")
    status_font.setPixelSize(T.FONT_SIZE_CAPTION_1)
    status_font.setWeight(QFont.Weight(T.FONT_WEIGHT_MEDIUM))
    painter.setFont(status_font)
    painter.setPen(body_color)
    painter.drawText(
        QRectF(66, 214, 270, 28),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        "Preparing your walkthrough studio…",
    )

    version_font = QFont("Segoe UI Variable")
    version_font.setPixelSize(T.FONT_SIZE_CAPTION_1)
    version_font.setWeight(QFont.Weight(T.FONT_WEIGHT_MEDIUM))
    painter.setFont(version_font)
    painter.setPen(body_color)
    painter.drawText(
        QRectF(344, 214, 94, 28),
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        f"Version {version}",
    )

    painter.end()
    return pixmap


class FollowCursorSplashScreen(QSplashScreen):
    """Frameless splash screen shown while the main window initializes."""

    def __init__(self, icon: QIcon, dark_mode: bool, version: str, parent: QWidget | None = None) -> None:
        flags = (
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(create_splash_pixmap(icon, dark_mode=dark_mode, version=version), flags)
        self.setParent(parent)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        """Ignore clicks so the splash cannot be dismissed accidentally."""
        event.ignore()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        """Ignore clicks so the splash stays up until startup completes."""
        event.ignore()


def show_startup_splash(app: QApplication, icon: QIcon, version: str) -> FollowCursorSplashScreen:
    """Create, show, and flush the startup splash before heavy initialization."""
    settings = QSettings("FollowCursor", "FollowCursor")
    dark_mode = settings.value("appearance/darkMode", True, type=bool)
    splash = FollowCursorSplashScreen(icon=icon, dark_mode=dark_mode, version=version)
    splash.show()
    app.processEvents()
    return splash


def finish_startup_splash(splash: QSplashScreen | None, window: QWidget) -> None:
    """Dismiss the splash once the main window is ready."""
    if splash is None:
        return
    splash.finish(window)
