"""Entry point for Commander application."""

import sys
from pathlib import Path


def setup_logging():
    """Setup application logging."""
    from commander.utils.logger import setup_logging as init_logging

    logger = init_logging()

    # Setup exception hook to log crashes
    def exception_hook(exc_type, exc_value, exc_tb):
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = exception_hook
    logger.info("Exception hook installed")
    return logger


# Initialize logging early
_logger = setup_logging()
_logger.info("Starting imports...")

try:
    _logger.debug("Importing PySide6.QtWidgets...")
    from PySide6.QtWidgets import QApplication

    _logger.debug("Importing PySide6.QtGui...")
    from PySide6.QtGui import QIcon

    _logger.debug("Importing PySide6.QtCore...")
    from PySide6.QtCore import QEvent

    _logger.debug("Importing MainWindow...")
    from commander.views.main_window import MainWindow

    _logger.debug("Importing i18n...")
    from commander.utils.i18n import tr

    _logger.debug("Importing image_loader...")
    # Supported image formats - import from image_loader for consistency
    from commander.core.image_loader import ALL_IMAGE_FORMATS as IMAGE_EXTENSIONS

    _logger.info("All imports completed successfully")
except Exception as e:
    _logger.critical(f"Failed to import modules: {e}", exc_info=True)
    raise


class WindowManager:
    """Manages multiple MainWindow instances."""

    _instance: "WindowManager | None" = None

    def __init__(self):
        self._windows: list[MainWindow] = []
        _logger.debug("WindowManager initialized")

    @classmethod
    def instance(cls) -> "WindowManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_window(self, path: Path | None = None) -> MainWindow:
        """Create a new window, optionally at a specific path."""
        _logger.info(f"Creating new window at path: {path}")
        try:
            _logger.debug("About to create MainWindow instance...")
            window = MainWindow()
            _logger.debug("MainWindow instance created")
            if path and path.exists() and path.is_dir():
                window._navigate_to(path)
                _logger.debug(f"Navigated to path: {path}")
            _logger.debug("Connecting destroyed signal...")
            window.destroyed.connect(lambda: self._on_window_destroyed(window))
            _logger.debug("Adding window to list...")
            self._windows.append(window)
            _logger.info(f"Window created successfully. Total windows: {len(self._windows)}")
            return window
        except Exception as e:
            _logger.critical(f"Failed to create window: {e}", exc_info=True)
            raise

    def _on_window_destroyed(self, window: MainWindow):
        """Remove window from list when destroyed."""
        if window in self._windows:
            self._windows.remove(window)

    def get_windows(self) -> list[MainWindow]:
        """Get all open windows."""
        return self._windows.copy()

    def close_all(self):
        """Close all windows."""
        for window in self._windows.copy():
            window.close()


def get_window_manager() -> WindowManager:
    """Get the singleton WindowManager instance."""
    return WindowManager.instance()


class CommanderApp(QApplication):
    """Custom QApplication to handle macOS file open events."""

    def __init__(self, argv):
        _logger.info("Creating QApplication...")
        super().__init__(argv)
        _logger.debug("QApplication created")
        self._pending_files: list[Path] = []
        self._viewer = None
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

        # Close all windows
        get_window_manager().close_all()

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
    _logger.info("main() started")

    # Get app name from i18n
    app_name = tr("app_name")
    _logger.debug(f"App name: {app_name}")

    # Set app info before creating QApplication for proper macOS menu bar
    if sys.platform == "darwin":
        _logger.debug("Setting up macOS bundle info...")
        # This must be done before QApplication is created
        try:
            from Foundation import NSBundle

            bundle = NSBundle.mainBundle()
            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
            if info:
                info["CFBundleName"] = app_name
            _logger.debug("macOS bundle info set")
        except ImportError:
            _logger.debug("pyobjc not installed, skipping bundle setup")

    _logger.info("Creating CommanderApp...")
    app = CommanderApp(sys.argv)
    app.setApplicationName(app_name)
    app.setApplicationDisplayName(app_name)
    app.setOrganizationName("HoneyCommander")
    _logger.debug("App properties set")

    # Set app icon
    _logger.debug("Setting app icon...")
    if getattr(sys, "frozen", False):
        # PyInstaller frozen app
        icon_path = Path(sys._MEIPASS) / "assets" / "icon.png"  # type: ignore
        _logger.debug(f"Frozen app icon path: {icon_path}")
    else:
        icon_path = Path(__file__).parent.parent.parent / "assets" / "icon.png"
        _logger.debug(f"Dev icon path: {icon_path}")

    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        _logger.debug("App icon set")
    else:
        _logger.warning(f"Icon not found: {icon_path}")

    _logger.info("Getting WindowManager...")
    wm = get_window_manager()

    # Check if an image file was passed as argument (command line)
    if len(sys.argv) > 1:
        arg_path = Path(sys.argv[1]).resolve()
        _logger.info(f"Command line argument: {arg_path}")

        if arg_path.exists() and is_image_file(arg_path):
            # Open image viewer directly
            _logger.info("Opening image viewer for file argument")
            app._open_image_viewer(arg_path)
            app._started = True
            _logger.info("Starting event loop (image viewer mode)")
            sys.exit(app.exec())
        elif arg_path.exists() and arg_path.is_dir():
            # Open main window at specified directory
            _logger.info(f"Opening window at directory: {arg_path}")
            window = wm.create_window(arg_path)
            window.show()
            _logger.info("Window shown")
            app._started = True
            _logger.info("Starting event loop (directory mode)")
            sys.exit(app.exec())

    # Check for pending files from macOS FileOpen events
    if app.process_pending_files():
        _logger.info("Processed pending files, starting event loop")
        sys.exit(app.exec())

    # Default: open main window
    _logger.info("Opening default main window...")
    window = wm.create_window()
    _logger.info("create_window returned, about to call show()...")
    window.show()
    _logger.info("show() completed, window should be visible")
    app._started = True

    _logger.info("Starting Qt event loop (app.exec())...")
    result = app.exec()
    _logger.info(f"Qt event loop ended with result: {result}")
    sys.exit(result)


if __name__ == "__main__":
    main()
