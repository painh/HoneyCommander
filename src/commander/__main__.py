"""Entry point for Commander application."""

import sys
import traceback
from pathlib import Path


def setup_crash_log():
    """Setup crash logging for frozen apps."""
    if getattr(sys, 'frozen', False):
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

from commander.views.main_window import MainWindow
from commander.utils.i18n import tr


# Supported image formats
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico", ".psd", ".psb"}


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

    app = QApplication(sys.argv)
    app.setApplicationName(app_name)
    app.setApplicationDisplayName(app_name)
    app.setOrganizationName("HoneyCommander")

    # Set app icon
    if getattr(sys, 'frozen', False):
        # PyInstaller frozen app
        icon_path = Path(sys._MEIPASS) / "assets" / "icon.png"
    else:
        icon_path = Path(__file__).parent.parent.parent / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Check if an image file was passed as argument
    if len(sys.argv) > 1:
        arg_path = Path(sys.argv[1]).resolve()

        if arg_path.exists() and is_image_file(arg_path):
            # Open image viewer directly
            from commander.views.fullscreen_viewer import FullscreenImageViewer

            # Get all images in the same folder
            images = get_images_in_folder(arg_path.parent)

            viewer = FullscreenImageViewer()
            viewer.closed.connect(app.quit)
            viewer.show_image(arg_path, images)

            sys.exit(app.exec())
        elif arg_path.exists() and arg_path.is_dir():
            # Open main window at specified directory
            window = MainWindow()
            window._navigate_to(arg_path)
            window.show()
            sys.exit(app.exec())

    # Default: open main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
