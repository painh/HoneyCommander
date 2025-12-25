"""Entry point for Commander application."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from commander.views.main_window import MainWindow


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
    app = QApplication(sys.argv)
    app.setApplicationName("Commander")
    app.setOrganizationName("Commander")

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
