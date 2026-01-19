"""Qt models for tag display and autocomplete."""

from typing import Optional, Any, List

from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QStringListModel

from ..core.asset_manager import Tag, get_tag_manager


class TagListModel(QAbstractListModel):
    """List model for displaying tags."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags: List[Tag] = []
        self._counts: dict[int, int] = {}

    def set_tags(self, tags: List[Tag], counts: Optional[dict[int, int]] = None) -> None:
        """Set the tags to display."""
        self.beginResetModel()
        self._tags = tags
        self._counts = counts or {}
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._tags)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        if row < 0 or row >= len(self._tags):
            return None

        tag = self._tags[row]

        if role == Qt.ItemDataRole.DisplayRole:
            count = self._counts.get(tag.id, 0)
            if count > 0:
                return f"{tag.full_name} ({count})"
            return tag.full_name

        elif role == Qt.ItemDataRole.UserRole:
            return tag.id

        elif role == Qt.ItemDataRole.UserRole + 1:
            return tag

        elif role == Qt.ItemDataRole.DecorationRole:
            # Could return a color swatch here
            pass

        elif role == Qt.ItemDataRole.ToolTipRole:
            parts = [tag.full_name]
            count = self._counts.get(tag.id, 0)
            if count > 0:
                parts.append(f"Used in {count} assets")
            return "\n".join(parts)

        return None

    def get_tag(self, row: int) -> Optional[Tag]:
        """Get tag by row index."""
        if 0 <= row < len(self._tags):
            return self._tags[row]
        return None


class TagCompleterModel(QStringListModel):
    """String list model for tag autocomplete."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._library_id: Optional[int] = None

    def set_library(self, library_id: Optional[int]) -> None:
        """Set library and load tags for autocomplete."""
        self._library_id = library_id
        self._load_tags()

    def _load_tags(self) -> None:
        """Load tag names for autocomplete."""
        if self._library_id is None:
            self.setStringList([])
            return

        tag_manager = get_tag_manager()
        tags = tag_manager.get_library_tags(self._library_id)
        tag_names = [t.full_name for t in tags]
        self.setStringList(tag_names)

    def refresh(self) -> None:
        """Refresh tag list."""
        self._load_tags()


class AllTagsModel(QAbstractListModel):
    """Model for displaying all tags with namespaces grouped."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[tuple[str, Optional[Tag]]] = []  # (display, tag or None for header)

    def load_all_tags(self) -> None:
        """Load all tags grouped by namespace."""
        self.beginResetModel()
        self._items = []

        tag_manager = get_tag_manager()
        all_tags = tag_manager.get_all_tags()

        # Group by namespace
        namespaces: dict[str, List[Tag]] = {}
        for tag in all_tags:
            ns = tag.namespace or ""
            if ns not in namespaces:
                namespaces[ns] = []
            namespaces[ns].append(tag)

        # Build items list
        for namespace in sorted(namespaces.keys()):
            # Add namespace header if not empty
            if namespace:
                self._items.append((f"── {namespace} ──", None))

            # Add tags
            for tag in sorted(namespaces[namespace], key=lambda t: t.name):
                self._items.append((tag.full_name, tag))

        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        if row < 0 or row >= len(self._items):
            return None

        display, tag = self._items[row]

        if role == Qt.ItemDataRole.DisplayRole:
            return display

        elif role == Qt.ItemDataRole.UserRole:
            return tag.id if tag else None

        elif role == Qt.ItemDataRole.UserRole + 1:
            return tag

        elif role == Qt.ItemDataRole.ForegroundRole:
            if tag is None:  # Header
                from PySide6.QtGui import QColor

                return QColor(128, 128, 128)

        elif role == Qt.ItemDataRole.FontRole:
            if tag is None:  # Header
                from PySide6.QtGui import QFont

                font = QFont()
                font.setBold(True)
                return font

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Headers are not selectable."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        row = index.row()
        if row < 0 or row >= len(self._items):
            return Qt.ItemFlag.NoItemFlags

        _, tag = self._items[row]
        if tag is None:  # Header
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
