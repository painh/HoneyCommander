"""Virtual file system model for network drives."""

import logging
from typing import Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QIcon

from commander.core.network import (
    ConnectionManager,
    NetworkEntry,
    NetworkHandler,
)

_logger = logging.getLogger(__name__)


class NetworkFileSystemModel(QAbstractItemModel):
    """Virtual file system model for network files.

    This model provides a tree structure for network file systems,
    supporting async loading and caching of directory contents.
    """

    # Signals
    loading_started = Signal(str)  # path
    loading_finished = Signal(str)  # path
    error_occurred = Signal(str)  # error message

    # Column definitions
    COLUMN_NAME = 0
    COLUMN_SIZE = 1
    COLUMN_TYPE = 2
    COLUMN_MODIFIED = 3
    COLUMN_COUNT = 4

    def __init__(
        self,
        connection_manager: ConnectionManager,
        connection_id: str,
        parent=None,
    ):
        """Initialize the model.

        Args:
            connection_manager: Connection manager to use.
            connection_id: ID of the connection.
            parent: Parent object.
        """
        super().__init__(parent)
        self._connection_manager = connection_manager
        self._connection_id = connection_id

        # Cache structure: path -> list of NetworkEntry
        self._cache: dict[str, list[NetworkEntry]] = {}
        self._loading_paths: set[str] = set()

        # Root entries (top level)
        self._root_entries: list[NetworkEntry] = []

        # Connect to connection manager signals
        self._connection_manager.entries_loaded.connect(self._on_entries_loaded)
        self._connection_manager.error_occurred.connect(self._on_error)

    @property
    def handler(self) -> NetworkHandler | None:
        """Get the network handler."""
        return self._connection_manager.get_handler(self._connection_id)

    def refresh(self, path: str = "/") -> None:
        """Refresh contents of a path.

        Args:
            path: Path to refresh.
        """
        # Clear cache for this path
        if path in self._cache:
            del self._cache[path]

        # Request new listing
        self._load_path(path)

    def _load_path(self, path: str) -> None:
        """Load contents of a path asynchronously."""
        if path in self._loading_paths:
            return

        self._loading_paths.add(path)
        self.loading_started.emit(path)
        self._connection_manager.list_entries_async(self._connection_id, path)

    def _on_entries_loaded(self, conn_id: str, path: str, entries: list[NetworkEntry]) -> None:
        """Handle loaded entries."""
        if conn_id != self._connection_id:
            return

        self._loading_paths.discard(path)

        # Sort entries: directories first, then by name
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))

        # Update cache
        self._cache[path] = entries

        # If this is root, update root entries
        if path == "/" or path == "":
            self.beginResetModel()
            self._root_entries = entries
            self.endResetModel()
        else:
            # Find parent index and notify of changes
            # For simplicity, we reset the model
            # A more efficient implementation would use dataChanged
            self.beginResetModel()
            self.endResetModel()

        self.loading_finished.emit(path)

    def _on_error(self, conn_id: str, error: str) -> None:
        """Handle errors."""
        if conn_id != self._connection_id:
            return

        self.error_occurred.emit(error)

    def get_entries(self, path: str) -> list[NetworkEntry]:
        """Get cached entries for a path.

        Args:
            path: Path to get entries for.

        Returns:
            List of entries, or empty list if not cached.
        """
        return self._cache.get(path, [])

    def get_entry_at_index(self, index: QModelIndex) -> NetworkEntry | None:
        """Get NetworkEntry at a model index.

        Args:
            index: Model index.

        Returns:
            NetworkEntry if valid, None otherwise.
        """
        if not index.isValid():
            return None

        return index.internalPointer()

    def get_path_at_index(self, index: QModelIndex) -> str | None:
        """Get path for a model index.

        Args:
            index: Model index.

        Returns:
            Path string if valid, None otherwise.
        """
        entry = self.get_entry_at_index(index)
        return entry.path if entry else None

    # QAbstractItemModel implementation

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        """Create index for item."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            # Root level
            if 0 <= row < len(self._root_entries):
                return self.createIndex(row, column, self._root_entries[row])
        else:
            # Child level
            parent_entry = parent.internalPointer()
            if parent_entry and parent_entry.is_dir:
                children = self._cache.get(parent_entry.path, [])
                if 0 <= row < len(children):
                    return self.createIndex(row, column, children[row])

        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        """Get parent index."""
        if not index.isValid():
            return QModelIndex()

        entry = index.internalPointer()
        if not entry:
            return QModelIndex()

        # Find parent path
        parent_path = "/".join(entry.path.rstrip("/").split("/")[:-1]) or "/"

        if parent_path == "/" or parent_path == "":
            return QModelIndex()

        # Find parent entry
        grandparent_path = "/".join(parent_path.rstrip("/").split("/")[:-1]) or "/"
        parent_name = parent_path.rstrip("/").split("/")[-1]

        parent_entries = self._cache.get(grandparent_path, self._root_entries)
        for i, e in enumerate(parent_entries):
            if e.name == parent_name:
                return self.createIndex(i, 0, e)

        return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of rows."""
        if not parent.isValid():
            return len(self._root_entries)

        entry = parent.internalPointer()
        if entry and entry.is_dir:
            # Check if we have cached children
            children = self._cache.get(entry.path, [])
            if children:
                return len(children)
            elif entry.path not in self._loading_paths:
                # Trigger async load
                self._load_path(entry.path)
            return 0

        return 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Get number of columns."""
        return self.COLUMN_COUNT

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Get data for index."""
        if not index.isValid():
            return None

        entry = index.internalPointer()
        if not entry:
            return None

        column = index.column()

        if role == Qt.DisplayRole:
            if column == self.COLUMN_NAME:
                return entry.name
            elif column == self.COLUMN_SIZE:
                if entry.is_dir:
                    return ""
                return self._format_size(entry.size)
            elif column == self.COLUMN_TYPE:
                if entry.is_dir:
                    return "Folder"
                # Get extension
                ext = entry.name.rsplit(".", 1)[-1] if "." in entry.name else ""
                return f"{ext.upper()} File" if ext else "File"
            elif column == self.COLUMN_MODIFIED:
                if entry.modified_time:
                    return entry.modified_time.strftime("%Y-%m-%d %H:%M")
                return ""

        elif role == Qt.DecorationRole:
            if column == self.COLUMN_NAME:
                if entry.is_dir:
                    return QIcon.fromTheme("folder")
                return QIcon.fromTheme("text-x-generic")

        elif role == Qt.UserRole:
            return entry

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        """Get header data."""
        if orientation != Qt.Horizontal or role != Qt.DisplayRole:
            return None

        headers = ["Name", "Size", "Type", "Modified"]
        if 0 <= section < len(headers):
            return headers[section]

        return None

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        """Check if item has children."""
        if not parent.isValid():
            return len(self._root_entries) > 0

        entry = parent.internalPointer()
        return entry.is_dir if entry else False

    def canFetchMore(self, parent: QModelIndex) -> bool:
        """Check if more children can be fetched."""
        if not parent.isValid():
            return False

        entry = parent.internalPointer()
        if entry and entry.is_dir:
            return entry.path not in self._cache and entry.path not in self._loading_paths

        return False

    def fetchMore(self, parent: QModelIndex) -> None:
        """Fetch more children."""
        if not parent.isValid():
            return

        entry = parent.internalPointer()
        if entry and entry.is_dir:
            self._load_path(entry.path)

    def _format_size(self, size: int) -> str:
        """Format file size for display."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.beginResetModel()
        self._cache.clear()
        self._root_entries.clear()
        self._loading_paths.clear()
        self.endResetModel()
