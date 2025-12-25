"""Preview panel - right panel."""

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
)
from PySide6.QtGui import QPixmap

from commander.core.image_loader import load_pixmap, ALL_IMAGE_FORMATS
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

        # Filter selector at top
        filter_layout = QHBoxLayout()
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

        layout.addLayout(filter_layout)

        # Scroll area for image
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._scroll_area.setWidget(self._image_label)

        # File info
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._scroll_area, stretch=3)
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
        self._image_label.clear()
        self._info_label.setText(tr("select_file_to_preview"))

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

        # Show image preview if applicable
        if path.is_file() and path.suffix.lower() in self.SUPPORTED_IMAGES:
            self._show_image_preview(path)
        else:
            self._image_label.clear()

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
