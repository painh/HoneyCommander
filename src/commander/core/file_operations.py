"""File operations (copy, paste, delete, etc.)."""

import shutil
from pathlib import Path

import send2trash


class FileOperations:
    """Handle file operations with clipboard support."""

    def __init__(self):
        self._clipboard: list[Path] = []
        self._clipboard_mode: str = "copy"  # "copy" or "cut"

    def copy_to_clipboard(self, paths: list[Path]):
        """Copy paths to internal clipboard."""
        self._clipboard = paths.copy()
        self._clipboard_mode = "copy"

    def cut_to_clipboard(self, paths: list[Path]):
        """Cut paths to internal clipboard."""
        self._clipboard = paths.copy()
        self._clipboard_mode = "cut"

    def paste(self, destination: Path) -> int:
        """Paste clipboard contents to destination."""
        if not self._clipboard:
            return 0

        count = 0
        for src in self._clipboard:
            try:
                if not src.exists():
                    continue

                dst = destination / src.name

                # Handle name conflicts
                dst = self._get_unique_path(dst)

                if self._clipboard_mode == "cut":
                    shutil.move(str(src), str(dst))
                else:
                    if src.is_dir():
                        shutil.copytree(str(src), str(dst))
                    else:
                        shutil.copy2(str(src), str(dst))
                count += 1
            except OSError:
                pass

        if self._clipboard_mode == "cut":
            self._clipboard.clear()

        return count

    def copy(self, sources: list[Path], destination: Path) -> int:
        """Copy files to destination."""
        count = 0
        for src in sources:
            try:
                if not src.exists():
                    continue

                dst = destination / src.name
                dst = self._get_unique_path(dst)

                if src.is_dir():
                    shutil.copytree(str(src), str(dst))
                else:
                    shutil.copy2(str(src), str(dst))
                count += 1
            except OSError:
                pass
        return count

    def move(self, sources: list[Path], destination: Path) -> int:
        """Move files to destination."""
        count = 0
        for src in sources:
            try:
                if not src.exists():
                    continue

                dst = destination / src.name
                dst = self._get_unique_path(dst)

                shutil.move(str(src), str(dst))
                count += 1
            except OSError:
                pass
        return count

    def delete(self, paths: list[Path], use_trash: bool = True) -> int:
        """Delete files (move to trash by default)."""
        count = 0
        for path in paths:
            try:
                if not path.exists():
                    continue

                if use_trash:
                    send2trash.send2trash(str(path))
                else:
                    if path.is_dir():
                        shutil.rmtree(str(path))
                    else:
                        path.unlink()
                count += 1
            except OSError:
                pass
        return count

    def rename(self, path: Path, new_name: str) -> Path | None:
        """Rename file or folder."""
        try:
            new_path = path.parent / new_name
            path.rename(new_path)
            return new_path
        except OSError:
            return None

    def create_folder(self, parent: Path, name: str) -> Path | None:
        """Create a new folder."""
        try:
            new_path = parent / name
            new_path.mkdir()
            return new_path
        except OSError:
            return None

    def _get_unique_path(self, path: Path) -> Path:
        """Get unique path by adding number suffix if needed."""
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1

        while True:
            new_name = f"{stem} ({counter}){suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
