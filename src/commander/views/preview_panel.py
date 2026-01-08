"""Preview panel - right panel."""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QSize, QFileSystemWatcher
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QComboBox,
    QStackedWidget,
    QPushButton,
)

from commander.core.image_loader import load_pixmap, ALL_IMAGE_FORMATS
from commander.widgets.text_viewer import TextViewer
from commander.utils.i18n import tr


class PreviewPanel(QWidget):
    """Right panel for file preview."""

    SUPPORTED_IMAGES = ALL_IMAGE_FORMATS

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path: Path | None = None
        self._smooth_filter: bool = False  # Crispy/sharp by default

        # File watcher for auto-refresh
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Filter selector at top (for images)
        self._filter_widget = QWidget()
        filter_layout = QHBoxLayout(self._filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 5)

        filter_label = QLabel(tr("filter") + ":")
        filter_label.setStyleSheet("font-size: 11px;")
        self._filter_combo = QComboBox()
        self._filter_combo.addItem(tr("filter_crispy"), False)  # Sharp/Crispy
        self._filter_combo.addItem(tr("filter_smooth"), True)  # Smooth
        self._filter_combo.setCurrentIndex(0)  # Crispy by default
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        self._filter_combo.setFixedWidth(100)

        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self._filter_combo)
        filter_layout.addStretch()

        layout.addWidget(self._filter_widget)

        # Stacked widget for different preview types
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, stretch=3)

        # === Image preview widget ===
        self._image_widget = QWidget()
        image_layout = QVBoxLayout(self._image_widget)
        image_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._scroll_area.setWidget(self._image_label)
        image_layout.addWidget(self._scroll_area)

        self._stack.addWidget(self._image_widget)

        # === Text preview widget ===
        self._text_widget = QWidget()
        text_layout = QVBoxLayout(self._text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self._text_viewer = TextViewer()
        self._text_viewer.content_modified.connect(self._on_text_modified)
        text_layout.addWidget(self._text_viewer)

        # Save button (hidden by default)
        self._save_button = QPushButton(tr("save"))
        self._save_button.clicked.connect(self._save_text_file)
        self._save_button.hide()
        text_layout.addWidget(self._save_button)

        self._stack.addWidget(self._text_widget)

        # === Large file widget ===
        self._large_file_widget = QWidget()
        large_layout = QVBoxLayout(self._large_file_widget)
        large_layout.setContentsMargins(10, 10, 10, 10)

        self._large_file_label = QLabel()
        self._large_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._large_file_label.setWordWrap(True)
        large_layout.addWidget(self._large_file_label)

        self._open_external_button = QPushButton(tr("open_with_external_app"))
        self._open_external_button.clicked.connect(self._open_with_external)
        large_layout.addWidget(self._open_external_button)
        large_layout.addStretch()

        self._stack.addWidget(self._large_file_widget)

        # === Placeholder widget ===
        self._placeholder_widget = QLabel()
        self._placeholder_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._placeholder_widget)

        # File info
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._info_label, stretch=1)

        # Show placeholder
        self._show_placeholder()

    def _on_filter_changed(self, index: int):
        """Handle filter selection change."""
        self._smooth_filter = self._filter_combo.currentData()
        # Refresh preview if we have an image
        if self._current_path and self._current_path.suffix.lower() in self.SUPPORTED_IMAGES:
            self._show_image_preview(self._current_path)

    def _show_placeholder(self):
        """Show placeholder when nothing is selected."""
        self._filter_widget.hide()
        self._placeholder_widget.setText(tr("select_file_to_preview"))
        self._stack.setCurrentWidget(self._placeholder_widget)
        self._info_label.clear()

    def show_preview(self, path: Path):
        """Show preview for selected file."""
        # Remove old watch
        if self._current_path and self._watcher.files():
            self._watcher.removePaths(self._watcher.files())

        self._current_path = path

        if not path.exists():
            self._show_placeholder()
            return

        # Watch this file for changes
        if path.is_file():
            self._watcher.addPath(str(path))

        # Show file info
        self._show_file_info(path)

        # Determine preview type
        if path.is_file() and path.suffix.lower() in self.SUPPORTED_IMAGES:
            # Image preview
            self._filter_widget.show()
            self._show_image_preview(path)
            self._stack.setCurrentWidget(self._image_widget)

        elif path.is_file() and TextViewer.is_text_file(path):
            # Text file
            self._filter_widget.hide()

            if TextViewer.is_too_large(path):
                # Too large - show open external button
                size = self._format_size(TextViewer.get_file_size(path))
                self._large_file_label.setText(
                    f"{tr('file_too_large')}\n\n"
                    f"{tr('size')}: {size}\n"
                    f"{tr('max_size')}: {self._format_size(TextViewer.MAX_FILE_SIZE)}"
                )
                self._stack.setCurrentWidget(self._large_file_widget)
            else:
                # Load text file
                self._text_viewer.load_file(path)
                self._save_button.hide()
                self._stack.setCurrentWidget(self._text_widget)

        else:
            # No preview available
            self._filter_widget.hide()
            self._placeholder_widget.setText(tr("no_preview_available"))
            self._stack.setCurrentWidget(self._placeholder_widget)

    def _on_file_changed(self, path: str):
        """Handle file change - refresh preview."""
        changed_path = Path(path)
        if self._current_path and changed_path == self._current_path:
            # Re-add to watcher (Qt removes it after change)
            if changed_path.exists():
                self._watcher.addPath(str(changed_path))
                self._show_image_preview(changed_path)
                self._show_file_info(changed_path)

    def _show_image_preview(self, path: Path):
        """Show image preview."""
        try:
            pixmap = load_pixmap(path)
            if not pixmap.isNull():
                # Scale to fit while maintaining aspect ratio
                transform_mode = (
                    Qt.TransformationMode.SmoothTransformation
                    if self._smooth_filter
                    else Qt.TransformationMode.FastTransformation
                )
                scaled = pixmap.scaled(
                    self._scroll_area.size() - QSize(20, 20),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    transform_mode,
                )
                self._image_label.setPixmap(scaled)
            else:
                self._image_label.setText(tr("cannot_load_image"))
        except Exception as e:
            self._image_label.setText(f"Error: {e}")

    def _show_file_info(self, path: Path):
        """Show file information."""
        try:
            stat = path.stat()
            size = self._format_size(stat.st_size)
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

            info_parts = [
                f"<b>{path.name}</b>",
                f"Size: {size}",
                f"Modified: {modified}",
            ]

            if path.is_file():
                info_parts.insert(1, f"Type: {path.suffix or 'File'}")

            self._info_label.setText("<br>".join(info_parts))
        except OSError as e:
            self._info_label.setText(f"Error: {e}")

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def resizeEvent(self, event):
        """Handle resize - rescale image."""
        super().resizeEvent(event)
        if self._current_path and self._current_path.suffix.lower() in self.SUPPORTED_IMAGES:
            self._show_image_preview(self._current_path)

    def _on_text_modified(self, is_modified: bool):
        """Handle text modification."""
        if is_modified:
            self._save_button.show()
        else:
            self._save_button.hide()

    def _save_text_file(self):
        """Save the text file."""
        if self._text_viewer.save_file():
            self._save_button.hide()

    def _open_with_external(self):
        """Open file with external application."""
        if not self._current_path:
            return

        if sys.platform == "darwin":
            subprocess.run(["open", str(self._current_path)])
        elif sys.platform == "win32":
            import os

            os.startfile(str(self._current_path))
        else:
            subprocess.run(["xdg-open", str(self._current_path)])
