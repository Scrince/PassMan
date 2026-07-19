from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QShowEvent
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget


def enable_resize_and_maximize(window: QWidget) -> None:
    """Allow mouse resize and the OS maximize/minimize controls on a top-level window."""
    flags = (
        window.windowFlags()
        | Qt.WindowType.WindowTitleHint
        | Qt.WindowType.WindowSystemMenuHint
        | Qt.WindowType.WindowMinMaxButtonsHint
        | Qt.WindowType.WindowCloseButtonHint
    )
    window.setWindowFlags(flags)
    # Clear any accidental maximum-size lock so the window can grow freely.
    window.setMaximumSize(16777215, 16777215)
    if isinstance(window, QDialog):
        window.setSizeGripEnabled(True)


def toggle_fullscreen(window: QWidget) -> None:
    if window.isFullScreen():
        window.showNormal()
    else:
        window.showFullScreen()


def center_widget_on_screen(window: QWidget) -> None:
    """Center a top-level window on the current/available screen."""
    screen = window.screen()
    if screen is None:
        app = QApplication.instance()
        screen = app.primaryScreen() if isinstance(app, QApplication) else None
    if screen is None:
        return
    available = screen.availableGeometry()
    frame = window.frameGeometry()
    width = frame.width() if frame.width() > 0 else max(window.width(), window.sizeHint().width())
    height = frame.height() if frame.height() > 0 else max(window.height(), window.sizeHint().height())
    x = available.x() + max(0, (available.width() - width) // 2)
    y = available.y() + max(0, (available.height() - height) // 2)
    window.move(x, y)


class ResizableDialog(QDialog):
    """QDialog that can be resized, maximized, and toggled fullscreen with F11."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        enable_resize_and_maximize(self)
        self._did_center = False

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._did_center:
            # Center after first show so maximize/title controls stay on-screen.
            center_widget_on_screen(self)
            self._did_center = True

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_F11:
            toggle_fullscreen(self)
            return
        super().keyPressEvent(event)


class ResizableMainWindow(QMainWindow):
    """QMainWindow that can be maximized and toggled fullscreen with F11."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        enable_resize_and_maximize(self)
        self.setMinimumSize(640, 480)
        self._did_center = False

    def showEvent(self, event: QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        if not self._did_center:
            center_widget_on_screen(self)
            self._did_center = True

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_F11:
            toggle_fullscreen(self)
            return
        super().keyPressEvent(event)
