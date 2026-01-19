"""Thumbnail delegate for asset browser with lazy loading.

Only loads thumbnails for items currently visible in the viewport.
Uses an LRU cache to manage memory efficiently.
"""

from pathlib import Path

from PySide6.QtCore import Qt, QModelIndex, QSize, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QAbstractItemView

from commander.core.thumbnail_provider import get_thumbnail_provider


class AssetThumbnailDelegate(QStyledItemDelegate):
    """Delegate for rendering asset thumbnails with lazy loading.

    Features:
    - Only loads thumbnails when items become visible
    - Uses global ThumbnailProvider for caching
    - Shows placeholder while loading
    - Displays filename below thumbnail
    """

    # Path role in the model (UserRole + 2 in AssetTableModel)
    PATH_ROLE = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QAbstractItemView = None):
        super().__init__(parent)
        self._view = parent
        self._thumbnail_size = QSize(128, 128)
        self._item_size = QSize(150, 170)

        # Connect to thumbnail provider
        self._provider = get_thumbnail_provider()
        self._provider.thumbnail_ready.connect(self._on_thumbnail_ready)

        # Track which paths are visible (for efficient updates)
        self._visible_paths: set[str] = set()

    def set_thumbnail_size(self, size: QSize) -> None:
        """Set thumbnail size."""
        self._thumbnail_size = size
        self._provider.set_thumbnail_size(size)

    def set_item_size(self, size: QSize) -> None:
        """Set total item size including label."""
        self._item_size = size

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QSize:
        """Return item size."""
        return self._item_size

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint the item with thumbnail and filename."""
        painter.save()

        # Get item data
        path = index.data(self.PATH_ROLE)
        name = index.data(Qt.ItemDataRole.DisplayRole) or ""

        # Calculate rects
        rect = option.rect
        thumb_rect = QRect(
            rect.x() + (rect.width() - self._thumbnail_size.width()) // 2,
            rect.y() + 4,
            self._thumbnail_size.width(),
            self._thumbnail_size.height(),
        )
        text_rect = QRect(
            rect.x() + 4,
            thumb_rect.bottom() + 4,
            rect.width() - 8,
            rect.height() - thumb_rect.height() - 12,
        )

        # Draw selection background
        if option.state & QStyleOptionViewItem.State_Selected:
            painter.fillRect(rect, option.palette.highlight())
        elif option.state & QStyleOptionViewItem.State_MouseOver:
            hover_color = option.palette.highlight().color()
            hover_color.setAlpha(50)
            painter.fillRect(rect, hover_color)

        # Draw thumbnail
        pixmap = self._get_thumbnail(path)
        if pixmap and not pixmap.isNull():
            # Center the pixmap in thumb_rect
            px = thumb_rect.x() + (thumb_rect.width() - pixmap.width()) // 2
            py = thumb_rect.y() + (thumb_rect.height() - pixmap.height()) // 2
            painter.drawPixmap(px, py, pixmap)
        else:
            # Draw placeholder
            self._draw_placeholder(painter, thumb_rect, path)

        # Draw filename
        if option.state & QStyleOptionViewItem.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        # Elide text if too long
        font_metrics = painter.fontMetrics()
        elided_text = font_metrics.elidedText(
            name, Qt.TextElideMode.ElideMiddle, text_rect.width()
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, elided_text)

        painter.restore()

    def _get_thumbnail(self, path: Path | None) -> QPixmap | None:
        """Get thumbnail for path, triggering load if needed."""
        if path is None or not isinstance(path, Path):
            return None

        # Track visible path
        self._visible_paths.add(str(path))

        # Request thumbnail (will return None if loading)
        return self._provider.get_thumbnail(path)

    def _draw_placeholder(
        self, painter: QPainter, rect: QRect, path: Path | None
    ) -> None:
        """Draw placeholder while thumbnail is loading."""
        # Draw background
        painter.fillRect(rect, QColor(60, 60, 60))

        # Draw border
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        # Draw loading indicator or icon based on file type
        if path and self._provider.is_supported(path):
            # Loading indicator
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "...")
        else:
            # Not an image
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "N/A")

    def _on_thumbnail_ready(self, path_str: str) -> None:
        """Handle thumbnail ready signal - update the view."""
        if self._view is None:
            return

        # Only update if this path is currently visible
        if path_str not in self._visible_paths:
            return

        # Find and update the item with this path
        # The view will only repaint visible items
        model = self._view.model()
        if model is None:
            return

        # Schedule viewport update - Qt will only repaint visible items
        self._view.viewport().update()

    def clear_visible_paths(self) -> None:
        """Clear visible paths tracking (call on scroll/resize)."""
        self._visible_paths.clear()
