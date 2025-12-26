"""Application logging utility."""

import logging
import sys
from datetime import datetime
from pathlib import Path

from commander.utils.settings import Settings

# Global logger instance
_logger: logging.Logger | None = None
_file_handler: logging.FileHandler | None = None


def get_log_path() -> Path:
    """Get the log file path (in the executable directory)."""
    if getattr(sys, "frozen", False):
        # PyInstaller frozen app - use executable directory
        exe_dir = Path(sys.executable).parent
        # On macOS, executable is inside .app bundle, go up to find the app location
        if sys.platform == "darwin" and ".app" in str(exe_dir):
            # Go up until we're outside the .app bundle
            while ".app" in str(exe_dir) and exe_dir.parent != exe_dir:
                exe_dir = exe_dir.parent
            exe_dir = exe_dir.parent  # One more to get out of .app
        return exe_dir / "HoneyCommander.log"
    else:
        # Development mode - use project root
        return Path(__file__).parent.parent.parent.parent / "HoneyCommander.log"


def setup_logging() -> logging.Logger:
    """Setup and return the application logger."""
    global _logger, _file_handler

    if _logger is not None:
        return _logger

    _logger = logging.getLogger("HoneyCommander")
    _logger.setLevel(logging.DEBUG)

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)
    _logger.addHandler(console_handler)

    # File handler (based on settings)
    settings = Settings()
    if settings.load_logging_enabled():
        _enable_file_logging()

    return _logger


def _enable_file_logging():
    """Enable file logging."""
    global _logger, _file_handler

    if _file_handler is not None or _logger is None:
        return

    log_path = get_log_path()

    try:
        # Overwrite log file each time (mode='w')
        _file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        _file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        _file_handler.setFormatter(file_formatter)
        _logger.addHandler(_file_handler)

        # Write startup info
        from commander import __version__, __build_date__

        _logger.info("=" * 50)
        _logger.info(f"HoneyCommander v{__version__}")
        if __build_date__:
            _logger.info(f"Build: {__build_date__}")
        _logger.info(f"Started: {datetime.now()}")
        _logger.info(f"Log file: {log_path}")
        _logger.info(f"Python: {sys.version}")
        _logger.info(f"Platform: {sys.platform}")
        _logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")
        _logger.info("=" * 50)
    except Exception as e:
        if _logger:
            _logger.warning(f"Could not create log file: {e}")


def _disable_file_logging():
    """Disable file logging."""
    global _logger, _file_handler

    if _file_handler is not None and _logger is not None:
        _logger.removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None


def set_logging_enabled(enabled: bool):
    """Enable or disable file logging."""
    settings = Settings()
    settings.save_logging_enabled(enabled)

    if enabled:
        _enable_file_logging()
    else:
        _disable_file_logging()


def get_logger() -> logging.Logger:
    """Get the application logger."""
    global _logger
    if _logger is None:
        return setup_logging()
    return _logger
