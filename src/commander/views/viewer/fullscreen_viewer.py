"""Fullscreen image viewer."""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QApplication,
    QMenu,
    QMessageBox,
    QInputDialog,
    QFileDialog,
    QScrollArea,
)
from PySide6.QtGui import (
    QPixmap,
    QKeyEvent,
    QWheelEvent,
    QTransform,
    QCursor,
)

from commander.core.image_loader import load_pixmap, ALL_IMAGE_FORMATS
from commander.utils.settings import Settings
from commander.views.viewer.animation_controller import AnimationController


class FullscreenImageViewer(QWidget):
    """Fullscreen image viewer with navigation."""

    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._settings = Settings()
        self._image_list: list[Path] = []
        self._current_index: int = 0
        self._zoom_level: float = 1.0
        self._original_pixmap: QPixmap | None = None
        self._displayed_pixmap: QPixmap | None = None
        self._rotation: int = 0
        self._flip_h: bool = False
        self._flip_v: bool = False
        self._pan_start: QPoint | None = None
        self._smooth_filter: bool = False
        self._info_overlay_visible: bool = False

        # Animation controller
        self._anim = AnimationController(self)
        self._anim.frame_changed.connect(self._on_anim_frame_changed)

        self._setup_ui()

    # ══════════════════════════════════════════════════════════════════════════
    # UI Setup
    # ══════════════════════════════════════════════════════════════════════════

    def _setup_ui(self) -> None:
        """Setup UI."""
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area for large images
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("QScrollArea { border: none; background-color: black; }")

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background-color: black;")
        self._scroll_area.setWidget(self._image_label)
        layout.addWidget(self._scroll_area, stretch=1)

        # Frame panel for animations
        self._setup_frame_panel(layout)

        # Info overlay
        self._info_overlay = QLabel(self)
        self._info_overlay.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 180); "
            "padding: 10px; font-family: monospace;"
        )
        self._info_overlay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._info_overlay.hide()

        # Info label (bottom)
        self._info_label = QLabel()
        self._info_label.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 180); padding: 8px;"
        )
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._info_label)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _setup_frame_panel(self, layout: QVBoxLayout) -> None:
        """Setup frame preview panel for animated images."""
        self._frame_panel = QWidget()
        self._frame_panel.setStyleSheet("background-color: rgba(0, 0, 0, 200);")
        self._frame_panel.setFixedHeight(100)
        self._frame_panel.hide()

        frame_layout = QHBoxLayout(self._frame_panel)
        frame_layout.setContentsMargins(10, 5, 10, 5)
        frame_layout.setSpacing(5)

        # Play/Pause button
        self._play_button = QLabel("▶")
        self._play_button.setStyleSheet("color: white; font-size: 24px; padding: 5px;")
        self._play_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_button.mousePressEvent = lambda e: self._toggle_animation()
        frame_layout.addWidget(self._play_button)

        # Frame scroll area
        self._frame_scroll = QScrollArea()
        self._frame_scroll.setWidgetResizable(True)
        self._frame_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._frame_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._frame_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._frame_container = QWidget()
        self._frame_container_layout = QHBoxLayout(self._frame_container)
        self._frame_container_layout.setContentsMargins(0, 0, 0, 0)
        self._frame_container_layout.setSpacing(3)
        self._frame_scroll.setWidget(self._frame_container)
        frame_layout.addWidget(self._frame_scroll, stretch=1)

        # Frame info
        self._frame_info = QLabel("0/0")
        self._frame_info.setStyleSheet("color: white; font-size: 14px; padding: 5px;")
        frame_layout.addWidget(self._frame_info)

        layout.addWidget(self._frame_panel)

    # ══════════════════════════════════════════════════════════════════════════
    # Public Methods
    # ══════════════════════════════════════════════════════════════════════════

    def show_image(self, path: Path, image_list: list[Path] | None = None) -> None:
        """Show image and optionally set image list for navigation."""
        self._image_list = image_list or [path]

        try:
            self._current_index = self._image_list.index(path)
        except ValueError:
            self._image_list = [path]
            self._current_index = 0

        self._reset_transform()
        self._load_current_image()
        self.showFullScreen()

    # ══════════════════════════════════════════════════════════════════════════
    # Image Loading
    # ══════════════════════════════════════════════════════════════════════════

    def _reset_transform(self) -> None:
        """Reset all transformations."""
        self._zoom_level = 1.0
        self._rotation = 0
        self._flip_h = False
        self._flip_v = False
        self._anim.stop()

    def _load_current_image(self) -> None:
        """Load and display current image."""
        if not self._image_list:
            return

        self._anim.stop()
        path = self._image_list[self._current_index]

        # Try loading as animation
        if self._anim.load(path):
            self._load_animated(path)
            return

        # Static image
        self._frame_panel.hide()
        self._original_pixmap = load_pixmap(path)

        if self._original_pixmap.isNull():
            self._image_label.setText(f"Cannot load: {path.name}")
            return

        self._zoom_level = self._get_fit_scale()
        self._update_display()
        self._update_info()

    def _load_animated(self, path: Path) -> None:
        """Setup animated image display."""
        self._original_pixmap = self._anim.get_current_pixmap()
        self._zoom_level = self._get_fit_scale()

        self._anim.start()
        self._play_button.setText("⏸")
        self._frame_panel.show()

        self._setup_frame_thumbnails()
        self._update_frame_info()
        self._update_info()

    def _setup_frame_thumbnails(self) -> None:
        """Create thumbnail placeholders and start generation."""
        # Clear existing
        while self._frame_container_layout.count():
            item = self._frame_container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Create placeholders
        thumb_size = self._anim.thumb_size
        for i in range(self._anim.frame_count):
            thumb_label = QLabel()
            thumb_label.setFixedSize(thumb_size, thumb_size)
            thumb_label.setStyleSheet("border: 2px solid transparent; background: #333;")
            thumb_label.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb_label.setProperty("frame_index", i)
            thumb_label.mousePressEvent = lambda e, idx=i: self._jump_to_frame(idx)
            self._frame_container_layout.addWidget(thumb_label)

        # Start background generation
        self._anim.start_thumbnail_generation(
            self._on_thumbnail_ready,
            self._on_thumbnails_finished,
        )

    def _on_thumbnail_ready(self, frame_index: int, pixmap: QPixmap) -> None:
        """Handle thumbnail ready from background thread."""
        if frame_index < self._frame_container_layout.count():
            item = self._frame_container_layout.itemAt(frame_index)
            if item and item.widget():
                widget = item.widget()
                widget.setPixmap(pixmap)  # type: ignore
                if frame_index == self._anim.current_frame:
                    widget.setStyleSheet("border: 2px solid #0078d4; background: #333;")

    def _on_thumbnails_finished(self) -> None:
        """Handle thumbnail generation finished."""
        pass

    def _on_anim_frame_changed(self, frame_number: int, pixmap: QPixmap) -> None:
        """Handle animation frame change."""
        if not pixmap.isNull():
            new_size = QSize(
                int(pixmap.width() * self._zoom_level),
                int(pixmap.height() * self._zoom_level),
            )
            scaled = pixmap.scaled(
                new_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
                if self._smooth_filter
                else Qt.TransformationMode.FastTransformation,
            )
            self._image_label.setPixmap(scaled)
            self._image_label.resize(scaled.size())

        self._update_frame_info()
        self._highlight_current_frame()

    def _highlight_current_frame(self) -> None:
        """Highlight current frame thumbnail."""
        current = self._anim.current_frame
        for i in range(self._frame_container_layout.count()):
            item = self._frame_container_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if widget.property("frame_index") == current:
                    widget.setStyleSheet("border: 2px solid #0078d4; background: #333;")
                    self._frame_scroll.ensureWidgetVisible(widget)
                else:
                    widget.setStyleSheet("border: 2px solid transparent; background: #333;")

    def _update_frame_info(self) -> None:
        """Update frame info label."""
        self._frame_info.setText(f"{self._anim.current_frame + 1}/{self._anim.frame_count}")

    # ══════════════════════════════════════════════════════════════════════════
    # Animation Controls
    # ══════════════════════════════════════════════════════════════════════════

    def _toggle_animation(self) -> None:
        """Toggle animation play/pause."""
        playing = self._anim.toggle()
        self._play_button.setText("⏸" if playing else "▶")

    def _jump_to_frame(self, frame_index: int) -> None:
        """Jump to specific frame."""
        pixmap = self._anim.jump_to_frame(frame_index, self._zoom_level, self._smooth_filter)
        if pixmap and not pixmap.isNull():
            new_size = QSize(
                int(pixmap.width() * self._zoom_level),
                int(pixmap.height() * self._zoom_level),
            )
            scaled = pixmap.scaled(
                new_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
                if self._smooth_filter
                else Qt.TransformationMode.FastTransformation,
            )
            self._image_label.setPixmap(scaled)
            self._image_label.resize(scaled.size())

        self._update_frame_info()
        self._highlight_current_frame()

    def _next_frame(self) -> None:
        """Go to next frame."""
        if self._anim.is_animated:
            next_idx = (self._anim.current_frame + 1) % self._anim.frame_count
            self._jump_to_frame(next_idx)

    def _prev_frame(self) -> None:
        """Go to previous frame."""
        if self._anim.is_animated:
            prev_idx = (self._anim.current_frame - 1) % self._anim.frame_count
            self._jump_to_frame(prev_idx)

    # ══════════════════════════════════════════════════════════════════════════
    # Display & Zoom
    # ══════════════════════════════════════════════════════════════════════════

    def _get_fit_scale(self) -> float:
        """Calculate scale to fit image to screen."""
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return 1.0
        transformed = self._get_transformed_pixmap()
        screen_size = QApplication.primaryScreen().size()
        return min(
            screen_size.width() / transformed.width(),
            screen_size.height() / transformed.height(),
        )

    def _get_transformed_pixmap(self) -> QPixmap:
        """Get pixmap with rotation and flip applied."""
        if self._original_pixmap is None:
            return QPixmap()

        transform = QTransform()
        if self._rotation != 0:
            transform.rotate(self._rotation)
        if self._flip_h:
            transform.scale(-1, 1)
        if self._flip_v:
            transform.scale(1, -1)

        if transform.isIdentity():
            return self._original_pixmap

        return self._original_pixmap.transformed(
            transform, Qt.TransformationMode.SmoothTransformation
        )

    def _update_display(self) -> None:
        """Update displayed image with current zoom."""
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return

        transformed = self._get_transformed_pixmap()
        new_size = QSize(
            int(transformed.width() * self._zoom_level),
            int(transformed.height() * self._zoom_level),
        )
        scaled = transformed.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
            if self._smooth_filter
            else Qt.TransformationMode.FastTransformation,
        )

        self._displayed_pixmap = scaled
        self._image_label.setPixmap(scaled)
        self._image_label.resize(scaled.size())

    def _update_info(self) -> None:
        """Update info label."""
        if not self._image_list:
            return

        path = self._image_list[self._current_index]
        total = len(self._image_list)
        current = self._current_index + 1
        zoom_percent = int(self._zoom_level * 100)

        # File size
        try:
            size = path.stat().st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / 1024 / 1024:.1f} MB"
        except OSError:
            size_str = ""

        # Resolution
        if self._original_pixmap and not self._original_pixmap.isNull():
            res_str = f"{self._original_pixmap.width()}x{self._original_pixmap.height()}"
        else:
            res_str = ""

        # Build info string
        info = f"{path.name} | {current}/{total} | {res_str} | {size_str} | {zoom_percent}%"
        if self._anim.is_animated:
            info += f" | 프레임 {self._anim.current_frame + 1}/{self._anim.frame_count}"
        self._info_label.setText(info)

    # ══════════════════════════════════════════════════════════════════════════
    # Transform Operations
    # ══════════════════════════════════════════════════════════════════════════

    def _rotate_clockwise(self) -> None:
        self._rotation = (self._rotation + 90) % 360
        self._update_display()
        self._update_info()

    def _rotate_counterclockwise(self) -> None:
        self._rotation = (self._rotation - 90) % 360
        self._update_display()
        self._update_info()

    def _flip_horizontal(self) -> None:
        self._flip_h = not self._flip_h
        self._update_display()

    def _flip_vertical(self) -> None:
        self._flip_v = not self._flip_v
        self._update_display()

    def _set_filter(self, smooth: bool) -> None:
        self._smooth_filter = smooth
        self._update_display()

    # ══════════════════════════════════════════════════════════════════════════
    # Navigation
    # ══════════════════════════════════════════════════════════════════════════

    def _next_image(self) -> None:
        if self._current_index < len(self._image_list) - 1:
            self._current_index += 1
            self._reset_transform()
            self._load_current_image()

    def _prev_image(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._reset_transform()
            self._load_current_image()

    def _zoom_in(self) -> None:
        if self._zoom_level < 10.0:
            self._zoom_level *= 1.25
            self._update_display()
            self._update_info()

    def _zoom_out(self) -> None:
        if self._zoom_level > 0.1:
            self._zoom_level /= 1.25
            self._update_display()
            self._update_info()

    def _zoom_fit(self) -> None:
        self._zoom_level = self._get_fit_scale()
        self._update_display()
        self._update_info()

    def _zoom_original(self) -> None:
        if self._original_pixmap is None:
            return
        self._zoom_level = 1.0
        self._update_display()
        self._update_info()

    def _show_zoom_dialog(self) -> None:
        current = int(self._zoom_level * 100)
        value, ok = QInputDialog.getInt(self, "확대/축소", "확대율 (%):", current, 10, 1000)
        if ok:
            self._zoom_level = value / 100.0
            self._update_display()
            self._update_info()

    # ══════════════════════════════════════════════════════════════════════════
    # File Operations
    # ══════════════════════════════════════════════════════════════════════════

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

    # ══════════════════════════════════════════════════════════════════════════
    # File Info
    # ══════════════════════════════════════════════════════════════════════════

    def _toggle_file_info(self) -> None:
        self._info_overlay_visible = not self._info_overlay_visible
        if self._info_overlay_visible:
            self._update_info_overlay()
            self._info_overlay.show()
        else:
            self._info_overlay.hide()

    def _update_info_overlay(self) -> None:
        if not self._image_list:
            return

        path = self._image_list[self._current_index]
        lines = [f"파일: {path.name}", f"경로: {path.parent}"]

        try:
            stat = path.stat()
            size = stat.st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / 1024 / 1024:.1f} MB"
            lines.append(f"크기: {size_str}")

            from datetime import datetime

            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"수정일: {mtime}")

            if hasattr(stat, "st_birthtime"):
                ctime = datetime.fromtimestamp(stat.st_birthtime).strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"생성일: {ctime}")
        except OSError:
            pass

        if self._original_pixmap and not self._original_pixmap.isNull():
            lines.append(
                f"해상도: {self._original_pixmap.width()} x {self._original_pixmap.height()}"
            )
            lines.append(f"비트 깊이: {self._original_pixmap.depth()}")

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            with Image.open(path) as img:
                lines.append(f"포맷: {img.format}")
                lines.append(f"모드: {img.mode}")

                exif_data = getattr(img, "_getexif", lambda: None)()
                if exif_data:
                    lines.extend(["", "=== EXIF ==="])
                    for tag_id, value in sorted(exif_data.items()):
                        tag = TAGS.get(tag_id, tag_id)
                        if isinstance(value, bytes) or (
                            isinstance(value, str) and len(value) > 100
                        ):
                            continue
                        lines.append(f"{tag}: {value}")
        except Exception:
            pass

        self._info_overlay.setText("\n".join(lines))
        self._info_overlay.adjustSize()
        self._info_overlay.move(10, 10)

    # ══════════════════════════════════════════════════════════════════════════
    # Context Menu
    # ══════════════════════════════════════════════════════════════════════════

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: white; border: 1px solid #555; }
            QMenu::item:selected { background-color: #0078d4; }
            QMenu::separator { height: 1px; background: #555; margin: 5px 0; }
        """)

        menu.addAction("열기 (F2)", self._open_file_dialog)
        menu.addAction("폴더 열기 (F)", self._open_folder)
        menu.addAction("닫기 (F4)", self.close)
        menu.addSeparator()

        menu.addAction("이미지 선택 (Enter)", self._select_image)
        menu.addAction("탐색기 열기 (Ctrl+Enter)", self._open_in_explorer)
        menu.addSeparator()

        filter_menu = menu.addMenu("필터 설정")
        no_filter = filter_menu.addAction("필터 없음 (U)")
        no_filter.setCheckable(True)
        no_filter.setChecked(not self._smooth_filter)
        no_filter.triggered.connect(lambda: self._set_filter(False))

        smooth_filter = filter_menu.addAction("부드럽게+선명하게 (S)")
        smooth_filter.setCheckable(True)
        smooth_filter.setChecked(self._smooth_filter)
        smooth_filter.triggered.connect(lambda: self._set_filter(True))
        menu.addSeparator()

        menu.addAction("이미지 이동...", self._move_image)

        process_menu = menu.addMenu("영상 처리")
        process_menu.addAction("시계방향 회전 (R)", self._rotate_clockwise)
        process_menu.addAction("반시계방향 회전 (Shift+R)", self._rotate_counterclockwise)
        process_menu.addSeparator()
        process_menu.addAction("좌우 반전 (H)", self._flip_horizontal)
        process_menu.addAction("상하 반전 (V)", self._flip_vertical)
        menu.addSeparator()

        view_menu = menu.addMenu("보기 모드")
        view_menu.addAction("화면에 맞추기 (9)", self._zoom_fit)
        view_menu.addAction("원본 크기 (0, 1)", self._zoom_original)
        view_menu.addSeparator()
        view_menu.addAction("확대 (+)", self._zoom_in)
        view_menu.addAction("축소 (-)", self._zoom_out)

        menu.addAction("축소/확대 보기", self._show_zoom_dialog)
        menu.addSeparator()

        folder_menu = menu.addMenu("폴더 이동")
        folder_menu.addAction("이전 폴더 ([)", self._prev_folder)
        folder_menu.addAction("다음 폴더 (])", self._next_folder)
        menu.addSeparator()

        menu.addAction("파일 정보/EXIF 정보 보기 (TAB)", self._toggle_file_info)
        menu.addSeparator()
        menu.addAction("파일 삭제 (Del)", self._delete_current)

        if sys.platform == "darwin":
            menu.addAction("사진 보관함으로 복사 (Ins)", self._copy_to_photos)

        menu.addAction("편집 프로그램 실행 (Ctrl+E)", self._open_in_editor)
        menu.addSeparator()
        menu.addAction("클립보드로 복사하기 (Ctrl+C)", self._copy_to_clipboard)
        menu.addSeparator()
        menu.addAction("종료 (X)", self.close)

        menu.exec(QCursor.pos())

    # ══════════════════════════════════════════════════════════════════════════
    # Event Handlers
    # ══════════════════════════════════════════════════════════════════════════

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key.Key_Escape, Qt.Key.Key_X, Qt.Key.Key_F4):
            self.close()
        elif key == Qt.Key.Key_Space:
            if self._anim.is_animated:
                self._toggle_animation()
            else:
                self._next_image()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            if self._anim.is_animated and modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._next_frame()
            else:
                self._next_image()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            if self._anim.is_animated and modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._prev_frame()
            else:
                self._prev_image()
        elif key == Qt.Key.Key_Backspace:
            self._prev_image()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._zoom_in()
        elif key == Qt.Key.Key_Minus:
            self._zoom_out()
        elif key == Qt.Key.Key_0:
            self._zoom_original()
        elif key == Qt.Key.Key_9:
            self._zoom_fit()
        elif key == Qt.Key.Key_1:
            self._zoom_original()
        elif key == Qt.Key.Key_Home:
            self._current_index = 0
            self._reset_transform()
            self._load_current_image()
        elif key == Qt.Key.Key_End:
            self._current_index = len(self._image_list) - 1
            self._reset_transform()
            self._load_current_image()
        elif key == Qt.Key.Key_R:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._rotate_counterclockwise()
            else:
                self._rotate_clockwise()
        elif key == Qt.Key.Key_H:
            self._flip_horizontal()
        elif key == Qt.Key.Key_V:
            self._flip_vertical()
        elif key == Qt.Key.Key_Delete:
            self._delete_current()
        elif key == Qt.Key.Key_Tab:
            self._toggle_file_info()
        elif key == Qt.Key.Key_F2:
            self._open_file_dialog()
        elif key == Qt.Key.Key_F:
            self._open_folder()
        elif key == Qt.Key.Key_U:
            self._set_filter(False)
        elif key == Qt.Key.Key_S:
            self._set_filter(True)
        elif key == Qt.Key.Key_C and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._copy_to_clipboard()
        elif key == Qt.Key.Key_E and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._open_in_editor()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self._open_in_explorer()
            else:
                self._select_image()
        elif key == Qt.Key.Key_Insert:
            if sys.platform == "darwin":
                self._copy_to_photos()
        elif key == Qt.Key.Key_BracketLeft:
            self._prev_folder()
        elif key == Qt.Key.Key_BracketRight:
            self._next_folder()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta > 0:
            self._prev_image()
        elif delta < 0:
            self._next_image()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pan_start = event.pos()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._zoom_fit()

    def mouseMoveEvent(self, event) -> None:
        if self._pan_start and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            h_bar = self._scroll_area.horizontalScrollBar()
            v_bar = self._scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pan_start = None

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)
