"""File operations mixin for file list view."""

from __future__ import annotations

import sys
import subprocess
import zipfile
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QInputDialog, QApplication


class FileListOperationsMixin:
    """Mixin providing file operations."""

    # Expected from main class
    _current_path: Path | None
    _viewer: object

    def _run_custom_command(self, cmd, path: Path) -> None:
        """Run a custom command."""
        from commander.utils.custom_commands import get_custom_commands_manager

        mgr = get_custom_commands_manager()
        if mgr.is_builtin_command(cmd):
            # Handle built-in commands
            if cmd.command == "__builtin__:image_viewer":
                self._open_builtin_image_viewer(path)
            elif cmd.command == "__builtin__:extract":
                self._extract_archive(path)
        else:
            cmd.execute(path)

    def _extract_archive(self, path: Path) -> None:
        """Extract archive to same directory."""
        from commander.core.archive_handler import ArchiveManager

        if not path.is_file():
            return

        # Extract to directory with same name as archive (without extension)
        extract_dir = path.parent / path.stem

        try:
            ArchiveManager.extract(path, extract_dir)
            # Refresh view
            if self._current_path:
                self.set_root_path(self._current_path)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Extract Error",
                f"Failed to extract archive:\n{e}",
            )

    def _extract_archives(self, paths: list[Path]) -> None:
        """Extract multiple archives to their respective directories."""
        from commander.core.archive_handler import ArchiveManager

        if not paths:
            return

        errors = []
        for path in paths:
            if not path.is_file():
                continue

            try:
                # Smart extract: if single top-level folder, extract directly
                # Otherwise, create folder named after archive
                ArchiveManager.smart_extract(path, path.parent)
            except Exception as e:
                errors.append(f"{path.name}: {e}")

        # Refresh view and restore selection to original archives
        if self._current_path:
            self.set_root_path(self._current_path)
            # Clear selection and re-select only the original archive files
            self._select_paths(paths)

        if errors:
            QMessageBox.warning(
                self,
                "Extract Error",
                "Failed to extract some archives:\n" + "\n".join(errors[:5]),
            )

    def _is_viewer_valid(self) -> bool:
        """Check if the viewer instance is still valid."""
        try:
            if not hasattr(self, "_viewer") or self._viewer is None:
                return False
            # Try to access a property to check if C++ object is still alive
            self._viewer.isVisible()
            return True
        except RuntimeError:
            return False

    def _get_or_create_viewer(self):
        """Get existing viewer or create a new one."""
        from commander.views.viewer import FullscreenImageViewer

        if not self._is_viewer_valid():
            self._viewer = FullscreenImageViewer(self.window())
        return self._viewer

    def _open_builtin_image_viewer(self, path: Path) -> None:
        """Open built-in image viewer."""
        from commander.core.image_loader import ALL_IMAGE_FORMATS
        from commander.core.archive_handler import ArchiveManager

        if path.is_dir():
            images = self._collect_images_from_dir(path, ALL_IMAGE_FORMATS)
            if images:
                path = images[0]
            else:
                return  # No images in directory
        elif ArchiveManager.is_archive(path):
            # Open archive in image viewer - viewer will handle extracting images
            viewer = self._get_or_create_viewer()
            viewer.show_archive(path)
            return
        else:
            # Get all images in same directory
            parent = path.parent
            images = sorted([p for p in parent.iterdir() if p.suffix.lower() in ALL_IMAGE_FORMATS])

        viewer = self._get_or_create_viewer()
        viewer.show_image(path, images)

    def _collect_images_from_dir(self, path: Path, formats: set) -> list[Path]:
        """Collect images from directory, optionally including subdirectories."""
        from commander.utils.i18n import tr

        # Check if there are subdirectories with images
        subdirs = [p for p in path.iterdir() if p.is_dir()]
        has_subdirs_with_images = False

        for subdir in subdirs:
            try:
                if any(p.suffix.lower() in formats for p in subdir.iterdir() if p.is_file()):
                    has_subdirs_with_images = True
                    break
            except PermissionError:
                continue

        include_subdirs = False
        if has_subdirs_with_images:
            reply = QMessageBox.question(
                self,
                tr("image_viewer_subfolders_title"),
                tr("image_viewer_subfolders_question"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            include_subdirs = reply == QMessageBox.StandardButton.Yes

        if include_subdirs:
            # Recursively collect all images
            images = []
            for p in sorted(path.rglob("*")):
                if p.is_file() and p.suffix.lower() in formats:
                    images.append(p)
            return images
        else:
            # Only current directory
            return sorted(
                [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in formats]
            )

    def _open_with_default(self, path: Path) -> None:
        """Open file with default application."""
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        elif sys.platform == "win32":
            import os

            os.startfile(str(path))
        else:
            subprocess.run(["xdg-open", str(path)])

    def _copy_files(self, paths: list[Path]) -> None:
        """Copy files to clipboard."""
        from commander.core.file_operations import FileOperations

        ops = FileOperations()
        ops.copy_to_clipboard(paths)

    def _cut_files(self, paths: list[Path]) -> None:
        """Cut files to clipboard."""
        from commander.core.file_operations import FileOperations

        ops = FileOperations()
        ops.cut_to_clipboard(paths)

    def _paste_files(self) -> None:
        """Paste files from clipboard."""
        from commander.core.file_operations import FileOperations
        from commander.widgets.progress_dialog import ProgressDialog

        if self._current_path is None:
            return

        ops = FileOperations()
        if not ops.has_clipboard():
            return

        # Use progress dialog for paste operation
        dialog = ProgressDialog("paste", [], self._current_path, self)
        dialog.exec()
        self.set_root_path(self._current_path)

    def _delete_files(self, paths: list[Path]) -> None:
        """Delete files."""
        from commander.core.file_operations import FileOperations

        if self._current_path is None:
            return

        reply = QMessageBox.question(
            self,
            "Delete",
            f"Move {len(paths)} item(s) to Trash?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ops = FileOperations()
            ops.delete(paths)
            self.set_root_path(self._current_path)

    def _create_new_folder(self) -> None:
        """Create new folder."""
        if self._current_path is None:
            return

        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            new_path = self._current_path / name
            try:
                new_path.mkdir()
                self.set_root_path(self._current_path)
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Cannot create folder: {e}")

    def _create_new_file(self) -> None:
        """Create a new empty file."""
        if self._current_path is None:
            return

        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if ok and name:
            new_path = self._current_path / name
            try:
                new_path.touch()
                self.set_root_path(self._current_path)
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Cannot create file: {e}")

    def _compress_files(self, paths: list[Path]) -> None:
        """Compress selected files to ZIP."""
        if self._current_path is None:
            return

        # Ask for zip file name
        default_name = paths[0].stem if len(paths) == 1 else "archive"
        name, ok = QInputDialog.getText(self, "Compress", "Archive name:", text=default_name)
        if not ok or not name:
            return

        zip_path = self._current_path / f"{name}.zip"

        # Check if exists
        if zip_path.exists():
            reply = QMessageBox.question(
                self,
                "Overwrite?",
                f"{zip_path.name} already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for path in paths:
                    if path.is_file():
                        zf.write(path, path.name)
                    elif path.is_dir():
                        for file in path.rglob("*"):
                            if file.is_file():
                                arcname = path.name / file.relative_to(path)
                                zf.write(file, arcname)

            self.set_root_path(self._current_path)
            QMessageBox.information(self, "Success", f"Created {zip_path.name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Compression failed: {e}")

    def _open_terminal(self) -> None:
        """Open terminal at current path."""
        path = self._current_path
        if path is None:
            return

        if sys.platform == "darwin":
            script = f'tell app "Terminal" to do script "cd {path}"'
            subprocess.run(["osascript", "-e", script])
        elif sys.platform == "win32":
            subprocess.Popen(
                ["powershell", "-NoExit", "-Command", f"cd '{path}'"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            for term in ["gnome-terminal", "konsole", "xterm"]:
                try:
                    subprocess.Popen([term, "--working-directory", str(path)])
                    break
                except FileNotFoundError:
                    continue

    def _reveal_in_finder(self, path: Path) -> None:
        """Reveal file/folder in Finder/Explorer."""
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(path)])
        else:
            subprocess.run(["xdg-open", str(path.parent)])

    def _copy_path(self, paths: list[Path]) -> None:
        """Copy file paths to clipboard."""
        clipboard = QApplication.clipboard()
        if len(paths) == 1:
            clipboard.setText(str(paths[0]))
        else:
            clipboard.setText("\n".join(str(p) for p in paths))

    def _show_info(self, path: Path) -> None:
        """Show file/folder info dialog."""
        from commander.widgets.info_dialog import InfoDialog

        dialog = InfoDialog(path, self)
        dialog.exec()

    def _quick_look(self, path: Path) -> None:
        """Open Quick Look preview (macOS only)."""
        if sys.platform == "darwin":
            subprocess.run(
                ["qlmanage", "-p", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

    def _on_files_dropped(self, paths: list[Path], destination: Path) -> None:
        """Handle files dropped from external app (e.g., Finder)."""
        from commander.widgets.progress_dialog import ProgressDialog

        if self._current_path is None:
            return

        # Filter out files that are already in the destination
        paths_to_copy = [p for p in paths if p.parent != destination]
        if not paths_to_copy:
            return

        # Ask user: Copy or Move?
        reply = QMessageBox.question(
            self,
            "Drop Files",
            f"Copy {len(paths_to_copy)} item(s) to this folder?\n\n"
            f"Click 'Yes' to copy, 'No' to move.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Cancel:
            return

        if reply == QMessageBox.StandardButton.Yes:
            # Copy
            dialog = ProgressDialog("copy", paths_to_copy, destination, self)
            dialog.exec()
        else:
            # Move
            dialog = ProgressDialog("move", paths_to_copy, destination, self)
            dialog.exec()

        self.set_root_path(self._current_path)
