"""Platform-specific trash handling with restore support."""

import sys
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TrashResult:
    """Result of a trash operation."""

    success: bool
    original_path: Path
    trash_path: Path | None = None  # Path in trash (for restore)
    error: str | None = None


class TrashHandler(ABC):
    """Abstract base class for platform-specific trash handlers."""

    @abstractmethod
    def trash(self, path: Path) -> TrashResult:
        """Move file/folder to trash. Returns TrashResult with trash location."""
        pass

    @abstractmethod
    def restore(self, original_path: Path, trash_path: Path) -> bool:
        """Restore file from trash to original location."""
        pass


class MacOSTrashHandler(TrashHandler):
    """macOS trash handler using NSFileManager."""

    def __init__(self):
        self._fm = None
        self._available = False
        try:
            from Foundation import NSFileManager, NSURL

            self._NSFileManager = NSFileManager
            self._NSURL = NSURL
            self._fm = NSFileManager.defaultManager()
            self._available = True
        except ImportError:
            pass

    def trash(self, path: Path) -> TrashResult:
        if not self._available:
            # Fallback to send2trash without restore support
            return self._fallback_trash(path)

        file_url = self._NSURL.fileURLWithPath_(str(path))
        success, result_url, error = self._fm.trashItemAtURL_resultingItemURL_error_(
            file_url, None, None
        )

        if success:
            trash_path = Path(result_url.path()) if result_url else None
            return TrashResult(
                success=True,
                original_path=path,
                trash_path=trash_path,
            )
        else:
            error_msg = str(error) if error else "Unknown error"
            return TrashResult(
                success=False,
                original_path=path,
                error=error_msg,
            )

    def restore(self, original_path: Path, trash_path: Path) -> bool:
        if not self._available or not trash_path or not trash_path.exists():
            return False

        trash_url = self._NSURL.fileURLWithPath_(str(trash_path))
        original_url = self._NSURL.fileURLWithPath_(str(original_path))

        # Ensure parent directory exists
        original_path.parent.mkdir(parents=True, exist_ok=True)

        success, error = self._fm.moveItemAtURL_toURL_error_(trash_url, original_url, None)
        return success

    def _fallback_trash(self, path: Path) -> TrashResult:
        """Fallback using send2trash (no restore support)."""
        try:
            import send2trash

            send2trash.send2trash(str(path))
            return TrashResult(
                success=True,
                original_path=path,
                trash_path=None,  # No restore support
            )
        except Exception as e:
            return TrashResult(
                success=False,
                original_path=path,
                error=str(e),
            )


class WindowsTrashHandler(TrashHandler):
    """Windows trash handler using winshell."""

    def __init__(self):
        self._available = False
        try:
            import winshell

            self._winshell = winshell
            self._available = True
        except ImportError:
            pass

    def trash(self, path: Path) -> TrashResult:
        if not self._available:
            return self._fallback_trash(path)

        try:
            # winshell.delete_file moves to recycle bin with allow_undo=True
            self._winshell.delete_file(
                str(path),
                allow_undo=True,
                no_confirm=True,
                silent=True,
            )
            return TrashResult(
                success=True,
                original_path=path,
                trash_path=path,  # Windows uses original path for restore
            )
        except Exception as e:
            return TrashResult(
                success=False,
                original_path=path,
                error=str(e),
            )

    def restore(self, original_path: Path, trash_path: Path) -> bool:
        if not self._available:
            return False

        try:
            # winshell can restore by original filepath
            self._winshell.undelete(str(original_path))
            return True
        except Exception:
            return False

    def _fallback_trash(self, path: Path) -> TrashResult:
        """Fallback using send2trash (no restore support)."""
        try:
            import send2trash

            send2trash.send2trash(str(path))
            return TrashResult(
                success=True,
                original_path=path,
                trash_path=None,
            )
        except Exception as e:
            return TrashResult(
                success=False,
                original_path=path,
                error=str(e),
            )


class LinuxTrashHandler(TrashHandler):
    """Linux trash handler using freedesktop.org trash spec."""

    def __init__(self):
        # Linux uses freedesktop.org trash specification
        # Files go to ~/.local/share/Trash/
        self._trash_dir = Path.home() / ".local" / "share" / "Trash"
        self._files_dir = self._trash_dir / "files"
        self._info_dir = self._trash_dir / "info"

    def trash(self, path: Path) -> TrashResult:
        try:
            import send2trash

            send2trash.send2trash(str(path))

            # Try to find the file in trash
            trash_path = self._files_dir / path.name
            if trash_path.exists():
                return TrashResult(
                    success=True,
                    original_path=path,
                    trash_path=trash_path,
                )
            else:
                # File might have been renamed due to collision
                return TrashResult(
                    success=True,
                    original_path=path,
                    trash_path=None,  # Can't determine exact location
                )
        except Exception as e:
            return TrashResult(
                success=False,
                original_path=path,
                error=str(e),
            )

    def restore(self, original_path: Path, trash_path: Path) -> bool:
        if not trash_path or not trash_path.exists():
            return False

        try:
            # Ensure parent directory exists
            original_path.parent.mkdir(parents=True, exist_ok=True)

            # Move from trash back to original location
            shutil.move(str(trash_path), str(original_path))

            # Remove .trashinfo file if exists
            info_file = self._info_dir / f"{trash_path.name}.trashinfo"
            if info_file.exists():
                info_file.unlink()

            return True
        except Exception:
            return False


def get_trash_handler() -> TrashHandler:
    """Get the appropriate trash handler for the current platform."""
    if sys.platform == "darwin":
        return MacOSTrashHandler()
    elif sys.platform == "win32":
        return WindowsTrashHandler()
    else:
        return LinuxTrashHandler()


# Singleton instance
_trash_handler: TrashHandler | None = None


def trash_handler() -> TrashHandler:
    """Get singleton trash handler instance."""
    global _trash_handler
    if _trash_handler is None:
        _trash_handler = get_trash_handler()
    return _trash_handler
