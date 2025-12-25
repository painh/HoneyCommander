"""File operations (copy, paste, delete, etc.)."""

import shutil
import threading
from pathlib import Path
from typing import Callable

import send2trash

from commander.core.undo_manager import get_undo_manager


class FileOperations:
    """Handle file operations with clipboard support (Singleton)."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._clipboard: list[Path] = []
        self._clipboard_mode: str = "copy"  # "copy" or "cut"
        self._initialized = True

    def copy_to_clipboard(self, paths: list[Path]):
        """Copy paths to internal clipboard."""
        self._clipboard = paths.copy()
        self._clipboard_mode = "copy"

    def cut_to_clipboard(self, paths: list[Path]):
        """Cut paths to internal clipboard."""
        self._clipboard = paths.copy()
        self._clipboard_mode = "cut"

    def has_clipboard(self) -> bool:
        """Check if clipboard has content."""
        return len(self._clipboard) > 0

    def get_clipboard_info(self) -> tuple[list[Path], str]:
        """Get clipboard contents and mode."""
        return self._clipboard.copy(), self._clipboard_mode

    def paste(self, destination: Path, progress_callback: Callable[[int, int, str], bool] | None = None) -> int:
        """Paste clipboard contents to destination.

        progress_callback(current, total, current_file) -> should_cancel
        """
        if not self._clipboard:
            return 0

        # Calculate total size for progress
        total_size = 0
        files_to_copy = []
        for src in self._clipboard:
            if src.exists():
                if src.is_dir():
                    for f in src.rglob("*"):
                        if f.is_file():
                            total_size += f.stat().st_size
                            files_to_copy.append((f, destination / src.name / f.relative_to(src)))
                else:
                    total_size += src.stat().st_size
                    files_to_copy.append((src, destination / src.name))

        copied_size = 0
        count = 0
        sources_for_undo = []
        dests_for_undo = []

        for src in self._clipboard:
            try:
                if not src.exists():
                    continue

                dst = destination / src.name
                dst = self._get_unique_path(dst)

                if self._clipboard_mode == "cut":
                    if progress_callback:
                        size = self._get_size(src)
                        if progress_callback(copied_size, total_size, src.name):
                            break  # Cancelled
                        copied_size += size
                    sources_for_undo.append(src)
                    shutil.move(str(src), str(dst))
                    dests_for_undo.append(dst)
                else:
                    if src.is_dir():
                        copied_size = self._copytree_with_progress(
                            src, dst, copied_size, total_size, progress_callback
                        )
                    else:
                        if progress_callback:
                            if progress_callback(copied_size, total_size, src.name):
                                break
                        shutil.copy2(str(src), str(dst))
                        copied_size += src.stat().st_size
                    sources_for_undo.append(src)
                    dests_for_undo.append(dst)
                count += 1
            except OSError:
                pass

        # Record for undo
        if count > 0:
            undo_mgr = get_undo_manager()
            if self._clipboard_mode == "cut":
                undo_mgr.record_move(sources_for_undo, dests_for_undo)
            else:
                undo_mgr.record_copy(sources_for_undo, dests_for_undo)

        if self._clipboard_mode == "cut":
            self._clipboard.clear()

        return count

    def _copytree_with_progress(
        self,
        src: Path,
        dst: Path,
        copied_size: int,
        total_size: int,
        progress_callback: Callable[[int, int, str], bool] | None
    ) -> int:
        """Copy directory tree with progress reporting."""
        dst.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            s = item
            d = dst / item.name

            if s.is_dir():
                copied_size = self._copytree_with_progress(
                    s, d, copied_size, total_size, progress_callback
                )
            else:
                if progress_callback:
                    if progress_callback(copied_size, total_size, s.name):
                        return copied_size  # Cancelled
                shutil.copy2(str(s), str(d))
                copied_size += s.stat().st_size

        return copied_size

    def _get_size(self, path: Path) -> int:
        """Get size of file or directory."""
        if path.is_file():
            return path.stat().st_size
        total = 0
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        return total

    def copy(self, sources: list[Path], destination: Path,
             progress_callback: Callable[[int, int, str], bool] | None = None) -> int:
        """Copy files to destination."""
        # Calculate total
        total_size = sum(self._get_size(s) for s in sources if s.exists())
        copied_size = 0
        count = 0
        sources_for_undo = []
        dests_for_undo = []

        for src in sources:
            try:
                if not src.exists():
                    continue

                dst = destination / src.name
                dst = self._get_unique_path(dst)

                if src.is_dir():
                    copied_size = self._copytree_with_progress(
                        src, dst, copied_size, total_size, progress_callback
                    )
                else:
                    if progress_callback:
                        if progress_callback(copied_size, total_size, src.name):
                            break
                    shutil.copy2(str(src), str(dst))
                    copied_size += src.stat().st_size
                sources_for_undo.append(src)
                dests_for_undo.append(dst)
                count += 1
            except OSError:
                pass

        # Record for undo
        if count > 0:
            get_undo_manager().record_copy(sources_for_undo, dests_for_undo)

        return count

    def move(self, sources: list[Path], destination: Path,
             progress_callback: Callable[[int, int, str], bool] | None = None) -> int:
        """Move files to destination."""
        total_size = sum(self._get_size(s) for s in sources if s.exists())
        moved_size = 0
        count = 0
        sources_for_undo = []
        dests_for_undo = []

        for src in sources:
            try:
                if not src.exists():
                    continue

                dst = destination / src.name
                dst = self._get_unique_path(dst)

                if progress_callback:
                    if progress_callback(moved_size, total_size, src.name):
                        break

                sources_for_undo.append(src)
                shutil.move(str(src), str(dst))
                dests_for_undo.append(dst)
                moved_size += self._get_size(dst)
                count += 1
            except OSError:
                pass

        # Record for undo
        if count > 0:
            get_undo_manager().record_move(sources_for_undo, dests_for_undo)

        return count

    def delete(self, paths: list[Path], use_trash: bool = True) -> int:
        """Delete files (move to trash by default)."""
        count = 0
        deleted_paths = []
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
                deleted_paths.append(path)
                count += 1
            except OSError:
                pass

        # Record for undo (note: delete from trash is not supported)
        if count > 0:
            get_undo_manager().record_delete(deleted_paths)

        return count

    def rename(self, path: Path, new_name: str) -> Path | None:
        """Rename file or folder."""
        try:
            new_path = path.parent / new_name
            old_path = path
            path.rename(new_path)
            # Record for undo
            get_undo_manager().record_rename(old_path, new_path)
            return new_path
        except OSError:
            return None

    def create_folder(self, parent: Path, name: str) -> Path | None:
        """Create a new folder."""
        try:
            new_path = parent / name
            new_path.mkdir()
            # Record for undo
            get_undo_manager().record_create_folder(new_path)
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
