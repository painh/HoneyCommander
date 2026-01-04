"""File operations (copy, paste, delete, etc.)."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Callable
from enum import Enum
from urllib.parse import unquote, urlparse

from commander.core.trash_handler import trash_handler
from commander.core.undo_manager import get_undo_manager


class ConflictResolution(Enum):
    """Resolution options for file conflicts."""

    SKIP = "skip"
    OVERWRITE = "overwrite"
    RENAME = "rename"  # Keep both (rename new file)
    CANCEL = "cancel"


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
        """Copy paths to internal and system clipboard."""
        self._clipboard = paths.copy()
        self._clipboard_mode = "copy"
        self._set_system_clipboard(paths)

    def cut_to_clipboard(self, paths: list[Path]):
        """Cut paths to internal and system clipboard."""
        self._clipboard = paths.copy()
        self._clipboard_mode = "cut"
        self._set_system_clipboard(paths)

    def _set_system_clipboard(self, paths: list[Path]):
        """Set files to system clipboard for external app paste (e.g., Finder)."""
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QMimeData, QUrl

            mime_data = QMimeData()
            urls = [QUrl.fromLocalFile(str(p)) for p in paths]
            mime_data.setUrls(urls)

            clipboard = QApplication.clipboard()
            clipboard.setMimeData(mime_data)
        except Exception:
            pass  # Silently fail if clipboard access fails

    def has_clipboard(self) -> bool:
        """Check if clipboard has content (internal or system)."""
        if len(self._clipboard) > 0:
            return True
        # Check system clipboard for files
        return len(self.get_system_clipboard_files()) > 0

    def get_system_clipboard_files(self) -> list[Path]:
        """Get files from system clipboard (e.g., Finder copy)."""
        try:
            from PySide6.QtWidgets import QApplication

            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()

            if mime_data is None:
                return []

            paths: list[Path] = []

            # Check for file URLs (macOS Finder, Linux file managers)
            if mime_data.hasUrls():
                for url in mime_data.urls():
                    if url.isLocalFile():
                        file_path = Path(url.toLocalFile())
                        if file_path.exists():
                            paths.append(file_path)

            # macOS: Also check for NSFilenamesPboardType via text/uri-list
            if not paths and mime_data.hasFormat("text/uri-list"):
                raw_data = mime_data.data("text/uri-list")
                uri_list = bytes(raw_data.data()).decode("utf-8")
                for line in uri_list.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("file://"):
                        parsed = urlparse(line)
                        file_path = Path(unquote(parsed.path))
                        if file_path.exists() and file_path not in paths:
                            paths.append(file_path)

            return paths
        except Exception:
            return []

    def get_clipboard_info(self) -> tuple[list[Path], str]:
        """Get clipboard contents and mode."""
        return self._clipboard.copy(), self._clipboard_mode

    def find_conflicts(self, sources: list[Path], destination: Path) -> list[tuple[Path, Path]]:
        """Find files that would conflict (already exist at destination).

        Returns list of (source, existing_destination) tuples.
        """
        conflicts = []
        for src in sources:
            if not src.exists():
                continue
            dst = destination / src.name
            if dst.exists():
                conflicts.append((src, dst))
        return conflicts

    def find_paste_conflicts(self, destination: Path) -> list[tuple[Path, Path]]:
        """Find conflicts for clipboard paste operation."""
        clipboard_files = self._clipboard if self._clipboard else self.get_system_clipboard_files()
        if not clipboard_files:
            return []
        return self.find_conflicts(clipboard_files, destination)

    def paste(
        self,
        destination: Path,
        progress_callback: Callable[[int, int, str], bool] | None = None,
        conflict_resolution: ConflictResolution = ConflictResolution.RENAME,
    ) -> int:
        """Paste clipboard contents to destination.

        progress_callback(current, total, current_file) -> should_cancel
        conflict_resolution: How to handle existing files
        """
        # Use internal clipboard if available, otherwise check system clipboard
        clipboard_files = self._clipboard if self._clipboard else self.get_system_clipboard_files()
        clipboard_mode = self._clipboard_mode if self._clipboard else "copy"

        if not clipboard_files:
            return 0

        if conflict_resolution == ConflictResolution.CANCEL:
            return 0

        # Calculate total size for progress
        total_size = 0
        files_to_copy = []
        for src in clipboard_files:
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

        for src in clipboard_files:
            try:
                if not src.exists():
                    continue

                dst = destination / src.name

                # Handle conflict based on resolution
                if dst.exists():
                    if conflict_resolution == ConflictResolution.SKIP:
                        continue  # Skip this file
                    elif conflict_resolution == ConflictResolution.OVERWRITE:
                        # Delete existing file/folder before copying
                        if dst.is_dir():
                            shutil.rmtree(str(dst))
                        else:
                            dst.unlink()
                    elif conflict_resolution == ConflictResolution.RENAME:
                        dst = self._get_unique_path(dst)

                if clipboard_mode == "cut":
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
            if clipboard_mode == "cut":
                undo_mgr.record_move(sources_for_undo, dests_for_undo)
            else:
                undo_mgr.record_copy(sources_for_undo, dests_for_undo)

        # Only clear internal clipboard if it was a cut operation from internal clipboard
        if clipboard_mode == "cut" and self._clipboard:
            self._clipboard.clear()

        return count

    def _copytree_with_progress(
        self,
        src: Path,
        dst: Path,
        copied_size: int,
        total_size: int,
        progress_callback: Callable[[int, int, str], bool] | None,
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

    def copy(
        self,
        sources: list[Path],
        destination: Path,
        progress_callback: Callable[[int, int, str], bool] | None = None,
        conflict_resolution: ConflictResolution = ConflictResolution.RENAME,
    ) -> int:
        """Copy files to destination."""
        if conflict_resolution == ConflictResolution.CANCEL:
            return 0

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

                # Handle conflict based on resolution
                if dst.exists():
                    if conflict_resolution == ConflictResolution.SKIP:
                        continue
                    elif conflict_resolution == ConflictResolution.OVERWRITE:
                        if dst.is_dir():
                            shutil.rmtree(str(dst))
                        else:
                            dst.unlink()
                    elif conflict_resolution == ConflictResolution.RENAME:
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

    def move(
        self,
        sources: list[Path],
        destination: Path,
        progress_callback: Callable[[int, int, str], bool] | None = None,
        conflict_resolution: ConflictResolution = ConflictResolution.RENAME,
    ) -> int:
        """Move files to destination."""
        if conflict_resolution == ConflictResolution.CANCEL:
            return 0

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

                # Handle conflict based on resolution
                if dst.exists():
                    if conflict_resolution == ConflictResolution.SKIP:
                        continue
                    elif conflict_resolution == ConflictResolution.OVERWRITE:
                        if dst.is_dir():
                            shutil.rmtree(str(dst))
                        else:
                            dst.unlink()
                    elif conflict_resolution == ConflictResolution.RENAME:
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
        deleted_paths: list[Path] = []
        trash_paths: list[Path | None] = []
        handler = trash_handler()

        for path in paths:
            try:
                if not path.exists():
                    continue

                if use_trash:
                    result = handler.trash(path)
                    if result.success:
                        deleted_paths.append(path)
                        trash_paths.append(result.trash_path)
                        count += 1
                else:
                    if path.is_dir():
                        shutil.rmtree(str(path))
                    else:
                        path.unlink()
                    deleted_paths.append(path)
                    trash_paths.append(None)  # No restore for permanent delete
                    count += 1
            except OSError:
                pass

        # Record for undo with trash paths for restore support
        if count > 0:
            get_undo_manager().record_delete(deleted_paths, trash_paths)

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
