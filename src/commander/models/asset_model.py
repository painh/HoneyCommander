"""Qt model for asset list display."""

from typing import Optional, Any

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QColor, QIcon, QPixmap

from ..core.asset_manager import Asset, get_library_manager
from ..core.thumbnail_provider import get_thumbnail_provider


class AssetTableModel(QAbstractTableModel):
    """Table model for displaying assets."""

    # Column definitions
    COLUMNS = ["Name", "Tags", "Rating", "Size", "Path"]
    COL_NAME = 0
    COL_TAGS = 1
    COL_RATING = 2
    COL_SIZE = 3
    COL_PATH = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._assets: list[Asset] = []
        self._library_id: Optional[int] = None
        self._thumbnail_provider = get_thumbnail_provider()
        self._thumbnail_provider.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._placeholder_icon: QIcon | None = None

    def _on_thumbnail_ready(self, path_str: str) -> None:
        """Handle thumbnail ready signal."""
        # Find the asset with this path and emit dataChanged
        for i, asset in enumerate(self._assets):
            if asset.current_path and str(asset.current_path) == path_str:
                idx = self.index(i, 0)
                self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DecorationRole])
                break

    def _get_placeholder_icon(self) -> QIcon:
        """Get placeholder icon for items without thumbnails."""
        if self._placeholder_icon is None:
            # Create a simple gray placeholder
            pixmap = QPixmap(128, 128)
            pixmap.fill(QColor(60, 60, 60))
            self._placeholder_icon = QIcon(pixmap)
        return self._placeholder_icon

    def set_library(self, library_id: Optional[int]) -> None:
        """Set the library and load assets."""
        self._library_id = library_id
        self.reload()

    def reload(
        self,
        tag_ids: Optional[list[int]] = None,
        rating_min: Optional[int] = None,
    ) -> None:
        """Reload assets with optional filters."""
        self.beginResetModel()

        if self._library_id is None:
            self._assets = []
        else:
            lib_manager = get_library_manager()
            self._assets = lib_manager.get_library_assets(
                self._library_id,
                tag_ids=tag_ids,
                rating_min=rating_min,
                include_missing=False,
            )

        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._assets)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if row < 0 or row >= len(self._assets):
            return None

        asset = self._assets[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_NAME:
                return asset.original_filename
            elif col == self.COL_TAGS:
                return ", ".join(asset.tags) if asset.tags else ""
            elif col == self.COL_RATING:
                return "★" * asset.rating if asset.rating > 0 else ""
            elif col == self.COL_SIZE:
                return self._format_size(asset.file_size)
            elif col == self.COL_PATH:
                return str(asset.current_path) if asset.current_path else "(missing)"

        elif role == Qt.ItemDataRole.UserRole:
            # Return asset ID for selection handling
            return asset.id

        elif role == Qt.ItemDataRole.UserRole + 1:
            # Return full asset object
            return asset

        elif role == Qt.ItemDataRole.UserRole + 2:
            # Return file path for thumbnail loading
            return asset.current_path

        elif role == Qt.ItemDataRole.ToolTipRole:
            lines = [asset.original_filename]
            if asset.tags:
                lines.append(f"Tags: {', '.join(asset.tags)}")
            if asset.rating > 0:
                lines.append(f"Rating: {'★' * asset.rating}")
            if asset.notes:
                lines.append(f"Notes: {asset.notes[:100]}...")
            return "\n".join(lines)

        elif role == Qt.ItemDataRole.ForegroundRole:
            if asset.is_missing:
                return QColor(180, 180, 180)  # Gray for missing

        elif role == Qt.ItemDataRole.DecorationRole:
            if col == self.COL_NAME:
                # Only load thumbnails for name column (grid view uses this)
                if asset.current_path and asset.current_path.exists():
                    pixmap = self._thumbnail_provider.get_thumbnail(asset.current_path)
                    if pixmap and not pixmap.isNull():
                        return QIcon(pixmap)
                # Return placeholder while loading or if no image
                return self._get_placeholder_icon()

        return None

    def _format_size(self, size: int) -> str:
        """Format file size for display."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def get_asset(self, row: int) -> Optional[Asset]:
        """Get asset by row index."""
        if 0 <= row < len(self._assets):
            return self._assets[row]
        return None

    def get_asset_by_id(self, asset_id: int) -> Optional[Asset]:
        """Get asset by ID."""
        for asset in self._assets:
            if asset.id == asset_id:
                return asset
        return None

    def get_row_by_id(self, asset_id: int) -> int:
        """Get row index by asset ID."""
        for i, asset in enumerate(self._assets):
            if asset.id == asset_id:
                return i
        return -1

    def update_asset(self, asset_id: int) -> None:
        """Refresh a single asset's data."""
        row = self.get_row_by_id(asset_id)
        if row < 0:
            return

        # Reload asset from database
        lib_manager = get_library_manager()
        updated = lib_manager.get_asset(asset_id)

        if updated:
            self._assets[row] = updated
            top_left = self.index(row, 0)
            bottom_right = self.index(row, len(self.COLUMNS) - 1)
            self.dataChanged.emit(top_left, bottom_right)


class AssetFilterProxyModel(QSortFilterProxyModel):
    """Filter proxy for asset model with text search."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_search_text(self, text: str) -> None:
        """Set search filter text."""
        self._search_text = text.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._search_text:
            return True

        model = self.sourceModel()
        if model is None:
            return True

        # Check name
        name_index = model.index(source_row, AssetTableModel.COL_NAME, source_parent)
        name = model.data(name_index, Qt.ItemDataRole.DisplayRole)
        if name and self._search_text in name.lower():
            return True

        # Check tags
        tags_index = model.index(source_row, AssetTableModel.COL_TAGS, source_parent)
        tags = model.data(tags_index, Qt.ItemDataRole.DisplayRole)
        if tags and self._search_text in tags.lower():
            return True

        return False

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Custom sorting for rating column."""
        if left.column() == AssetTableModel.COL_RATING:
            # Sort by rating value, not string
            left_asset = left.data(Qt.ItemDataRole.UserRole + 1)
            right_asset = right.data(Qt.ItemDataRole.UserRole + 1)
            if left_asset and right_asset:
                return left_asset.rating < right_asset.rating

        elif left.column() == AssetTableModel.COL_SIZE:
            # Sort by actual file size
            left_asset = left.data(Qt.ItemDataRole.UserRole + 1)
            right_asset = right.data(Qt.ItemDataRole.UserRole + 1)
            if left_asset and right_asset:
                return left_asset.file_size < right_asset.file_size

        return super().lessThan(left, right)
