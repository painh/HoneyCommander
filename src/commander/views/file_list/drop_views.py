"""Drop-enabled view widgets for file list."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTreeView, QListView
from PySide6.QtGui import QDragEnterEvent, QDropEvent


class DropEnabledTreeView(QTreeView):
    """TreeView that handles external file drops."""

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
    """ListView that handles external file drops."""

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
