"""Entry point for Commander application."""

import sys
import traceback
from pathlib import Path


def setup_crash_log():
    """Setup crash logging for frozen apps."""
    if getattr(sys, "frozen", False):
        log_path = Path.home() / "HoneyCommander_crash.log"

        def exception_hook(exc_type, exc_value, exc_tb):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"Crash at: {__import__('datetime').datetime.now()}\n\n")
                f.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
            sys.__excepthook__(exc_type, exc_value, exc_tb)

        sys.excepthook = exception_hook


setup_crash_log()

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QEvent

from commander.views.main_window import MainWindow
from commander.utils.i18n import tr


# Supported image formats - import from image_loader for consistency
from commander.core.image_loader import ALL_IMAGE_FORMATS as IMAGE_EXTENSIONS


class CommanderApp(QApplication):
    """Custom QApplication to handle macOS file open events."""

    def __init__(self, argv):
        super().__init__(argv)
        self._pending_files: list[Path] = []
        self._viewer = None
        self._main_window = None
        self._started = False

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FileOpen:
            from PySide6.QtGui import QFileOpenEvent

            file_event: QFileOpenEvent = event  # type: ignore
            file_path = Path(file_event.file()).resolve()
            if file_path.exists() and is_image_file(file_path):
                if self._started:
                    # App already running, open viewer immediately
                    self._open_image_viewer(file_path)
                else:
                    # App starting, queue the file
                    self._pending_files.append(file_path)
            return True
        return super().event(event)

    def process_pending_files(self):
        """Process any files that were queued during startup."""
        self._started = True
        if self._pending_files:
            self._open_image_viewer(self._pending_files[0])
            self._pending_files.clear()
            return True
        return False

    def _open_image_viewer(self, image_path: Path):
        """Open the fullscreen image viewer."""
        from commander.views.viewer import FullscreenImageViewer

        # Close main window if open
        if self._main_window:
            self._main_window.close()
            self._main_window = None

        # Get all images in the same folder
        images = get_images_in_folder(image_path.parent)

        if self._viewer is None:
            self._viewer = FullscreenImageViewer()
            self._viewer.closed.connect(self.quit)

        self._viewer.show_image(image_path, images)


def is_image_file(path: Path) -> bool:
    """Check if path is a supported image file."""
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def get_images_in_folder(folder: Path) -> list[Path]:
    """Get all image files in folder, sorted."""
    images = [p for p in folder.iterdir() if is_image_file(p)]
    images.sort()
    return images


def main():
    # Get app name from i18n
    app_name = tr("app_name")

    # Set app info before creating QApplication for proper macOS menu bar
    if sys.platform == "darwin":
        # This must be done before QApplication is created
        try:
            from Foundation import NSBundle

            bundle = NSBundle.mainBundle()
            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
            if info:
                info["CFBundleName"] = app_name
        except ImportError:
            pass  # pyobjc not installed

    app = CommanderApp(sys.argv)
    app.setApplicationName(app_name)
    app.setApplicationDisplayName(app_name)
    app.setOrganizationName("HoneyCommander")

    # Set app icon
    if getattr(sys, "frozen", False):
        # PyInstaller frozen app
        icon_path = Path(sys._MEIPASS) / "assets" / "icon.png"  # type: ignore
    else:
        icon_path = Path(__file__).parent.parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Check if an image file was passed as argument (command line)
    if len(sys.argv) > 1:
        arg_path = Path(sys.argv[1]).resolve()

        if arg_path.exists() and is_image_file(arg_path):
            # Open image viewer directly
            app._open_image_viewer(arg_path)
            app._started = True
            sys.exit(app.exec())
        elif arg_path.exists() and arg_path.is_dir():
            # Open main window at specified directory
            window = MainWindow()
            window._navigate_to(arg_path)
            window.show()
            app._main_window = window
            app._started = True
            sys.exit(app.exec())

    # Check for pending files from macOS FileOpen events
    if app.process_pending_files():
        sys.exit(app.exec())

    # Default: open main window
    window = MainWindow()
    window.show()
    app._main_window = window
    app._started = True

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
