"""File operations mixin for fullscreen viewer."""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox, QFileDialog, QApplication

from commander.core.image_loader import ALL_IMAGE_FORMATS

if TYPE_CHECKING:
    from PySide6.QtGui import QPixmap


class ViewerFileOpsMixin:
    """Mixin providing file operations for the viewer."""

    # These attributes are expected from the main class
    _image_list: list[Path]
    _current_index: int
    _original_pixmap: "QPixmap | None"
    _get_transformed_pixmap: callable

    def _get_images_in_folder(self, folder: Path) -> list[Path]:
        """Get all images in folder."""
        images = [
            p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ALL_IMAGE_FORMATS
        ]
        images.sort()
        return images

    def _get_sibling_folders(self) -> list[Path]:
        """Get sibling folders that contain images."""
        if not self._image_list:
            return []

        current_folder = self._image_list[self._current_index].parent
        parent = current_folder.parent

        try:
            folders = sorted(
                [f for f in parent.iterdir() if f.is_dir() and self._get_images_in_folder(f)]
            )
            return folders
        except (PermissionError, OSError):
            return [current_folder]

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "이미지 열기",
            str(self._image_list[self._current_index].parent)
            if self._image_list
            else str(Path.home()),
            "Images (*.jpg *.jpeg *.png *.gif *.bmp *.webp *.tiff);;All Files (*)",
        )
        if path:
            new_path = Path(path)
            self._image_list = [new_path]
            self._current_index = 0
            self._reset_transform()
            self._load_current_image()

    def _open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "폴더 열기",
            str(self._image_list[self._current_index].parent)
            if self._image_list
            else str(Path.home()),
        )
        if folder:
            images = self._get_images_in_folder(Path(folder))
            if images:
                self._image_list = images
                self._current_index = 0
                self._reset_transform()
                self._load_current_image()

    def _prev_folder(self) -> None:
        if not self._image_list:
            return
        current_folder = self._image_list[self._current_index].parent
        folders = self._get_sibling_folders()
        if not folders:
            return
        try:
            idx = folders.index(current_folder)
            if idx > 0:
                images = self._get_images_in_folder(folders[idx - 1])
                if images:
                    self._image_list = images
                    self._current_index = 0
                    self._reset_transform()
                    self._load_current_image()
        except ValueError:
            pass

    def _next_folder(self) -> None:
        if not self._image_list:
            return
        current_folder = self._image_list[self._current_index].parent
        folders = self._get_sibling_folders()
        if not folders:
            return
        try:
            idx = folders.index(current_folder)
            if idx < len(folders) - 1:
                images = self._get_images_in_folder(folders[idx + 1])
                if images:
                    self._image_list = images
                    self._current_index = 0
                    self._reset_transform()
                    self._load_current_image()
        except ValueError:
            pass

    def _select_image(self) -> None:
        self.close()

    def _open_in_explorer(self) -> None:
        if not self._image_list:
            return
        path = self._image_list[self._current_index]
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(path)])
        else:
            subprocess.run(["xdg-open", str(path.parent)])

    def _move_image(self) -> None:
        if not self._image_list:
            return
        path = self._image_list[self._current_index]
        dest = QFileDialog.getExistingDirectory(self, "이미지 이동", str(path.parent))
        if dest:
            import shutil

            try:
                new_path = Path(dest) / path.name
                shutil.move(str(path), str(new_path))
                self._image_list.pop(self._current_index)
                if not self._image_list:
                    self.close()
                    return
                if self._current_index >= len(self._image_list):
                    self._current_index = len(self._image_list) - 1
                self._load_current_image()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"이동 실패: {e}")

    def _delete_current(self) -> None:
        if not self._image_list:
            return
        path = self._image_list[self._current_index]
        reply = QMessageBox.question(
            self,
            "삭제 확인",
            f"'{path.name}'을(를) 휴지통으로 이동하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                import send2trash

                send2trash.send2trash(str(path))
                self._image_list.pop(self._current_index)
                if not self._image_list:
                    self.close()
                    return
                if self._current_index >= len(self._image_list):
                    self._current_index = len(self._image_list) - 1
                self._load_current_image()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"삭제 실패: {e}")

    def _copy_to_photos(self) -> None:
        if not self._image_list or sys.platform != "darwin":
            return
        path = self._image_list[self._current_index]
        try:
            subprocess.run(
                ["osascript", "-e", f'tell application "Photos" to import POSIX file "{path}"']
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"복사 실패: {e}")

    def _open_in_editor(self) -> None:
        if not self._image_list:
            return
        path = self._image_list[self._current_index]
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Preview", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["mspaint", str(path)])
        else:
            subprocess.run(["gimp", str(path)])

    def _copy_to_clipboard(self) -> None:
        if self._original_pixmap and not self._original_pixmap.isNull():
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(self._get_transformed_pixmap())
