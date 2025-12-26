"""Drop-enabled view widgets for file list."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTreeView, QListView, QAbstractItemView
from PySide6.QtGui import QDragEnterEvent, QDropEvent


class DragDropMixin:
    """Mixin class for drag and drop functionality.

    Provides:
    - Drag out to external apps (files/folders)
    - Drop from external apps
    - Internal drag and drop
    """

    files_dropped = Signal(list, Path)  # dropped files, destination
    _current_path: Path | None = None

    def setup_drag_drop(self) -> None:
        """Setup drag and drop settings. Call this in __init__ after super()."""
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def set_current_path(self, path: Path) -> None:
        """Set current directory path for drops."""
        self._current_path = path

    def get_drag_paths(self) -> list[Path]:
        """Get paths of selected items for dragging. Override in subclass."""
        return []

    def handle_drag_enter(self, event: QDragEnterEvent) -> bool:
        """Handle drag enter. Returns True if handled."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return True
        return False

    def handle_drag_move(self, event) -> bool:
        """Handle drag move. Returns True if handled."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return True
        return False

    def handle_drop(self, event: QDropEvent, dest_path: Path | None = None) -> bool:
        """Handle drop. Returns True if handled."""
        target = dest_path or self._current_path
        if event.mimeData().hasUrls() and target:
            urls = event.mimeData().urls()
            paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths, target)
                event.acceptProposedAction()
                return True
        return False


# Need to import Qt here to avoid circular import
from PySide6.QtCore import Qt


class DropEnabledTreeView(QTreeView):
    """TreeView that handles drag and drop."""

    files_dropped = Signal(list, Path)  # dropped files, destination

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._current_path: Path | None = None

    def set_current_path(self, path: Path) -> None:
        """Set current directory path for drops."""
        self._current_path = path

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter - accept file drops from external apps."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        """Handle drag move."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop - copy/move files from external apps."""
        if event.mimeData().hasUrls() and self._current_path:
            urls = event.mimeData().urls()
            paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths, self._current_path)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class DropEnabledListView(QListView):
    """ListView that handles drag and drop."""

    files_dropped = Signal(list, Path)  # dropped files, destination

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._current_path: Path | None = None

    def set_current_path(self, path: Path) -> None:
        """Set current directory path for drops."""
        self._current_path = path

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter - accept file drops from external apps."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        """Handle drag move."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop - copy/move files from external apps."""
        if event.mimeData().hasUrls() and self._current_path:
            urls = event.mimeData().urls()
            paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths, self._current_path)
                event.acceptProposedAction()
                return
        super().dropEvent(event)
