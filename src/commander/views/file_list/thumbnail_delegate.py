"""Thumbnail delegate for displaying image thumbnails in file list."""

from pathlib import Path

from PySide6.QtCore import Qt, QModelIndex, QRect
from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtGui import QPainter, QColor

from commander.core.thumbnail_provider import get_thumbnail_provider
from commander.utils.themes import get_file_color


class ThumbnailDelegate(QStyledItemDelegate):
    """Custom delegate for displaying image thumbnails."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumbnail_provider = get_thumbnail_provider()
        self._thumbnail_provider.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._view = parent

    def _on_thumbnail_ready(self, path_str: str) -> None:
        """Handle thumbnail ready - trigger repaint."""
        if self._view:
            self._view.viewport().update()

    def _get_text_color(self, file_path: Path, option, is_selected: bool) -> QColor:
        """Get text color based on file type."""
        if is_selected:
            return option.palette.highlightedText().color()

        color_hex = get_file_color(file_path)
        if color_hex:
            return QColor(color_hex)

        return option.palette.text().color()

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        """Paint the item with thumbnail if available."""
        # Get file path from model
        model = index.model()
        file_path = Path(model.filePath(index))

        # Check if it's an image and we have a thumbnail
        thumbnail = None
        if file_path.is_file() and self._thumbnail_provider.is_supported(file_path):
            thumbnail = self._thumbnail_provider.get_thumbnail(file_path)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)

        if thumbnail:
            # Draw selection background
            if is_selected:
                painter.fillRect(option.rect, option.palette.highlight())

            # Calculate centered position for thumbnail
            thumb_rect = QRect(
                option.rect.x() + (option.rect.width() - thumbnail.width()) // 2,
                option.rect.y() + 5,
                thumbnail.width(),
                thumbnail.height(),
            )
            painter.drawPixmap(thumb_rect, thumbnail)

            # Draw filename below thumbnail
            text_rect = QRect(
                option.rect.x(),
                option.rect.y() + option.rect.height() - 35,
                option.rect.width(),
                30,
            )

            text_color = self._get_text_color(file_path, option, is_selected)
            painter.setPen(text_color)

            file_name = model.fileName(index)
            elided = painter.fontMetrics().elidedText(
                file_name, Qt.TextElideMode.ElideMiddle, text_rect.width() - 4
            )
            painter.drawText(
                text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, elided
            )
        else:
            # Default painting for non-images
            super().paint(painter, option, index)
