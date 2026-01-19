"""Fullscreen image viewer."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QInputDialog,
    QScrollArea,
)
from PySide6.QtGui import QPixmap, QTransform, QCursor

from commander.core.image_loader import load_pixmap, ALL_IMAGE_FORMATS
from commander.utils.settings import Settings
from commander.views.viewer.animation_controller import AnimationController
from commander.views.viewer.grid_overlay import GridOverlay
from commander.views.viewer.image_cache import ImageCache, ArchiveImageEntry, load_pixmap_from_bytes
from commander.views.viewer.viewer_file_ops import ViewerFileOpsMixin
from commander.views.viewer.viewer_input_handler import ViewerInputHandlerMixin


class FullscreenImageViewer(ViewerInputHandlerMixin, ViewerFileOpsMixin, QWidget):
    """Fullscreen image viewer with navigation."""

    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

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

        # Archive mode
        self._archive_mode: bool = False
        self._archive_images: list[ArchiveImageEntry] = []
        self._archive_handler = None

        # Animation controller
        self._anim = AnimationController(self)
        self._anim.frame_changed.connect(self._on_anim_frame_changed)

        # Grid overlay settings
        self._grid_visible = self._settings.load_viewer_grid_visible()
        self._grid_size = self._settings.load_viewer_grid_size()

        # Image cache for preloading
        self._preload_count = self._settings.load_image_preload_count()
        self._image_cache = ImageCache(self)
        self._image_cache.set_max_size(self._preload_count * 2 + 1)
        self._image_cache.image_loaded.connect(self._on_image_preloaded)

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

        # Grid overlay - parent is image_label so it follows the image
        self._grid_overlay = GridOverlay(self._image_label)
        self._grid_overlay.set_grid_size(self._grid_size)
        self._grid_overlay.set_grid_visible(self._grid_visible)

        # Info overlay - parent is scroll_area's viewport so it stays on top of image
        self._info_overlay = QLabel(self._scroll_area.viewport())
        self._info_overlay.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 180); "
            "padding: 10px; font-family: 'Menlo', 'Monaco', 'Courier New', monospace;"
        )
        self._info_overlay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._info_overlay.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
        # Exit archive mode
        self._archive_mode = False
        self._archive_images = []
        self._close_archive_handler()

        self._image_list = image_list or [path]

        try:
            self._current_index = self._image_list.index(path)
        except ValueError:
            self._image_list = [path]
            self._current_index = 0

        self._reset_transform()
        self._load_current_image()
        self._show_with_saved_mode()

    def show_archive(self, archive_path: Path) -> None:
        """Show images from an archive file."""
        from commander.core.archive_handler import ArchiveManager

        # Close previous handler if any
        self._close_archive_handler()

        # Open archive
        handler = ArchiveManager.get_handler(archive_path)
        if not handler:
            QMessageBox.warning(self, "Error", f"Cannot open archive: {archive_path.name}")
            return

        self._archive_handler = handler

        # Collect all image files from archive (recursively)
        image_entries = self._collect_archive_images(archive_path, handler, "")

        if not image_entries:
            handler.close()
            self._archive_handler = None
            QMessageBox.information(self, "Info", "No images found in archive.")
            return

        # Sort by path
        image_entries.sort(key=lambda e: e.internal_path.lower())

        self._archive_mode = True
        self._archive_images = image_entries
        self._image_list = []  # Clear normal image list
        self._current_index = 0

        self._reset_transform()
        self._load_current_image()
        self._show_with_saved_mode()

    def _collect_archive_images(
        self, archive_path: Path, handler, internal_path: str
    ) -> list[ArchiveImageEntry]:
        """Recursively collect all image files from archive."""
        entries = []
        for entry in handler.list_entries(internal_path):
            if entry.is_dir:
                # Recurse into subdirectory
                entries.extend(self._collect_archive_images(archive_path, handler, entry.path))
            else:
                # Check if it's an image file
                suffix = Path(entry.name).suffix.lower()
                if suffix in ALL_IMAGE_FORMATS:
                    entries.append(
                        ArchiveImageEntry(
                            archive_path=archive_path,
                            internal_path=entry.path,
                            name=entry.name,
                        )
                    )
        return entries

    def _close_archive_handler(self) -> None:
        """Close archive handler if open."""
        if self._archive_handler:
            try:
                self._archive_handler.close()
            except Exception:
                pass
            self._archive_handler = None

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
        self._anim.stop()
        self._frame_panel.hide()

        if self._archive_mode:
            # Load from archive (no caching for archives yet)
            if not self._archive_images:
                return
            entry = self._archive_images[self._current_index]
            self._original_pixmap = self._load_archive_image(entry)
        else:
            # Load from filesystem
            if not self._image_list:
                return
            path = self._image_list[self._current_index]

            # Try loading as animation
            if self._anim.load(path):
                self._load_animated(path)
                self._preload_nearby_images()
                return

            # Try to get from cache first
            cached = self._image_cache.get(path)
            if cached is not None:
                self._original_pixmap = cached
            else:
                self._original_pixmap = load_pixmap(path)
                # Cache current image
                if self._original_pixmap and not self._original_pixmap.isNull():
                    self._image_cache.put(path, self._original_pixmap)

            # Preload nearby images
            self._preload_nearby_images()

        if self._original_pixmap is None or self._original_pixmap.isNull():
            name = (
                self._archive_images[self._current_index].name
                if self._archive_mode
                else self._image_list[self._current_index].name
            )
            self._image_label.setText(f"Cannot load: {name}")
            return

        self._zoom_level = self._get_fit_scale()
        self._update_display()
        self._update_info()

        # Update info overlay if visible
        if self._info_overlay_visible:
            self._update_info_overlay()

    def _preload_nearby_images(self) -> None:
        """Preload images before and after current index."""
        if self._archive_mode or not self._image_list or self._preload_count == 0:
            return

        total = len(self._image_list)
        for offset in range(1, self._preload_count + 1):
            # Preload next images
            next_idx = self._current_index + offset
            if next_idx < total:
                self._image_cache.preload(self._image_list[next_idx])

            # Preload previous images
            prev_idx = self._current_index - offset
            if prev_idx >= 0:
                self._image_cache.preload(self._image_list[prev_idx])

    def _on_image_preloaded(self, path: Path, pixmap: QPixmap) -> None:
        """Handle preloaded image from background thread."""
        self._image_cache.put(path, pixmap)

    def _load_archive_image(self, entry: ArchiveImageEntry) -> QPixmap:
        """Load image from archive."""
        if not self._archive_handler:
            return QPixmap()

        try:
            data = self._archive_handler.read_file(entry.internal_path)
            return load_pixmap_from_bytes(data)
        except Exception as e:
            print(f"Error loading {entry.internal_path}: {e}")
            return QPixmap()

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

        # Update info overlay if visible
        if self._info_overlay_visible:
            self._update_info_overlay()

    def _setup_frame_thumbnails(self) -> None:
        """Create thumbnail placeholders and start generation."""
        # Clear existing
        while self._frame_container_layout.count():
            item = self._frame_container_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()

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
            widget = item.widget() if item else None
            if widget and isinstance(widget, QLabel):
                widget.setPixmap(pixmap)
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
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
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
        """Calculate scale to fit image to window."""
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return 1.0
        transformed = self._get_transformed_pixmap()
        # Use scroll area size (actual viewport) instead of screen size
        viewport_size = self._scroll_area.size()
        # Account for info label height
        available_height = viewport_size.height()
        return min(
            viewport_size.width() / transformed.width(),
            available_height / transformed.height(),
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

        # Update grid overlay size to match image
        self._grid_overlay.setGeometry(0, 0, scaled.width(), scaled.height())

    def _update_info(self) -> None:
        """Update info label."""
        if self._archive_mode:
            if not self._archive_images:
                return
            entry = self._archive_images[self._current_index]
            total = len(self._archive_images)
            current = self._current_index + 1
            zoom_percent = int(self._zoom_level * 100)

            # Resolution
            if self._original_pixmap and not self._original_pixmap.isNull():
                res_str = f"{self._original_pixmap.width()}x{self._original_pixmap.height()}"
            else:
                res_str = ""

            # Build info string for archive mode
            archive_name = entry.archive_path.name
            info = f"[{archive_name}] {entry.internal_path} | {current}/{total} | {res_str} | {zoom_percent}%"
            self._info_label.setText(info)
            return

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

    def _toggle_grid(self) -> None:
        """Toggle grid overlay visibility."""
        self._grid_visible = not self._grid_visible
        self._grid_overlay.set_grid_visible(self._grid_visible)
        self._settings.save_viewer_grid_visible(self._grid_visible)

    def _change_grid_size(self) -> None:
        """Show dialog to change grid size."""
        size, ok = QInputDialog.getInt(
            self,
            "그리드 크기",
            "그리드 크기 (픽셀):",
            self._grid_size,
            4,  # min
            256,  # max
            1,  # step
        )
        if ok:
            self._grid_size = size
            self._grid_overlay.set_grid_size(size)
            self._settings.save_viewer_grid_size(size)

    # ══════════════════════════════════════════════════════════════════════════
    # Navigation
    # ══════════════════════════════════════════════════════════════════════════

    def _get_total_images(self) -> int:
        """Get total number of images."""
        if self._archive_mode:
            return len(self._archive_images)
        return len(self._image_list)

    def _next_image(self) -> None:
        total = self._get_total_images()
        if self._current_index < total - 1:
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
    # File Info
    # ══════════════════════════════════════════════════════════════════════════

    def _toggle_file_info(self) -> None:
        """Toggle file info overlay visibility."""
        self._info_overlay_visible = not self._info_overlay_visible

        if self._info_overlay_visible:
            self._update_info_overlay()
            self._info_overlay.show()
            self._info_overlay.raise_()
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

        # Show cached images info
        cached_paths = self._image_cache.get_cached_paths()
        if cached_paths:
            lines.extend(["", "=== 캐시된 이미지 ==="])
            for cached_path in cached_paths:
                if cached_path == path:
                    # Current image - highlight with marker
                    lines.append(f"▶ {cached_path.name} (현재)")
                else:
                    lines.append(f"  {cached_path.name}")

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

        # Grid menu
        grid_menu = menu.addMenu("그리드")
        grid_toggle = grid_menu.addAction("그리드 표시 (G)")
        grid_toggle.setCheckable(True)
        grid_toggle.setChecked(self._grid_overlay.is_grid_visible())
        grid_toggle.triggered.connect(self._toggle_grid)
        grid_menu.addSeparator()
        grid_menu.addAction(
            f"그리드 크기 변경... (현재: {self._grid_size}px)", self._change_grid_size
        )
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
    # Event Handlers (close event)
    # ══════════════════════════════════════════════════════════════════════════

    def closeEvent(self, event) -> None:
        self._close_archive_handler()
        self.closed.emit()
        super().closeEvent(event)
