"""Preview panel - right panel."""

from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtGui import QPixmap, QImage


class PreviewPanel(QWidget):
    """Right panel for file preview."""

    SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Scroll area for image
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored
        )
        self._scroll_area.setWidget(self._image_label)

        # File info
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._scroll_area, stretch=3)
        layout.addWidget(self._info_label, stretch=1)

        # Show placeholder
        self._show_placeholder()

    def _show_placeholder(self):
        """Show placeholder when nothing is selected."""
        self._image_label.clear()
        self._info_label.setText("Select a file to preview")

    def show_preview(self, path: Path):
        """Show preview for selected file."""
        self._current_path = path

        if not path.exists():
            self._show_placeholder()
            return

        # Show file info
        self._show_file_info(path)

        # Show image preview if applicable
        if path.is_file() and path.suffix.lower() in self.SUPPORTED_IMAGES:
            self._show_image_preview(path)
        else:
            self._image_label.clear()

    def _show_image_preview(self, path: Path):
        """Show image preview."""
        try:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                # Scale to fit while maintaining aspect ratio
                scaled = pixmap.scaled(
                    self._scroll_area.size() - QSize(20, 20),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._image_label.setPixmap(scaled)
            else:
                self._image_label.setText("Cannot load image")
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
