"""FollowCursor — screen recorder with cinematic cursor-following zoom."""

import logging
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor, QIcon
from PySide6.QtCore import QAbstractNativeEventFilter, qInstallMessageHandler, QtMsgType
from app.main_window import MainWindow
from app.icon import create_app_icon, get_ico_path
from app.version import __version__

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s | %(levelname)s | %(message)s",
)

_logger = logging.getLogger(__name__)


def _global_exception_handler(exc_type, exc_value, exc_tb):
    """Log unhandled exceptions instead of crashing silently."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


# Suppress Qt's internal "QFont::setPointSize: Point size <= 0" warnings
# that fire during DPI transitions between monitors with different scale
# factors. All our code uses setPixelSize / font-size: Npx — the -1 comes
# from Qt's stylesheet engine recalculating during the transition.
_original_handler = None


def _message_handler(msg_type, context, message):
    """Custom Qt message handler that suppresses harmless DPI warnings."""
    if "QFont::setPointSize" in message:
        return  # suppress
    if _original_handler:
        _original_handler(msg_type, context, message)
    else:
        # Default: print to stderr like Qt does
        if msg_type != QtMsgType.QtDebugMsg:
            print(message, file=sys.stderr)


class _WinCloseFilter(QAbstractNativeEventFilter):
    """Intercept WM_CLOSE at the application level so taskbar close works
    even when a modal dialog is open."""

    def __init__(self, main_window):
        super().__init__()
        self._main_window = main_window

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            try:
                import ctypes, ctypes.wintypes
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x0010:  # WM_CLOSE
                    # Close any open modal dialog first (e.g. source picker)
                    modal = QApplication.activeModalWidget()
                    if modal:
                        modal.close()
                    self._main_window.close()
                    return True, 0
            except Exception:
                pass
        return False, 0


def main() -> None:
    """Application entry point — creates QApplication, applies theme, shows MainWindow."""
    sys.excepthook = _global_exception_handler

    # Suppress QFont::setPointSize warnings from Qt's stylesheet DPI recalc
    global _original_handler
    _original_handler = qInstallMessageHandler(_message_handler)

    # Set Windows AppUserModelID so the taskbar uses our icon, not Python's
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "FollowCursor.FollowCursor.1"
        )

    app = QApplication(sys.argv)
    app.setApplicationName("FollowCursor")
    app.setApplicationVersion(__version__)

    # Build QIcon from painted pixmaps
    icon = create_app_icon()

    # Also generate a real .ico file and add it — Windows taskbar needs this
    try:
        ico_path = get_ico_path()
        ico_icon = QIcon(ico_path)
        # Merge: the .ico gets priority for the taskbar
        for sz in ico_icon.availableSizes():
            icon.addPixmap(ico_icon.pixmap(sz))
    except Exception:
        pass  # fall back to QPainter-rendered pixmaps

    app.setWindowIcon(icon)

    # dark palette base (QSS handles the rest)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1b1a2e"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e4e4ed"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#131221"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#201f34"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e4e4ed"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#28263e"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e4e4ed"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#8b5cf6"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    window = MainWindow()
    window.show()

    # Install native event filter for taskbar close support
    if sys.platform == "win32":
        close_filter = _WinCloseFilter(window)
        app.installNativeEventFilter(close_filter)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
