"""Folder tree view - left panel."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QDir, QModelIndex
from PySide6.QtWidgets import QTreeView, QFileSystemModel, QAbstractItemView
from PySide6.QtGui import QDragEnterEvent, QDropEvent


class FolderTreeView(QTreeView):
    """Left panel folder tree view with drag and drop support."""

    folder_selected = Signal(Path)
    files_dropped = Signal(list, Path)  # dropped files, destination folder

    def __init__(self, parent=None):
        super().__init__(parent)

        self._model = QFileSystemModel()
        self._model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot)
        self.setModel(self._model)

        # Only show name column
        for i in range(1, self._model.columnCount()):
            self.hideColumn(i)

        # Setup root based on platform
        self._setup_root()

        # Appearance
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setIndentation(20)

        # Enable drag and drop
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

        # Signals
        self.clicked.connect(self._on_clicked)

    def _setup_root(self):
        """Setup root path based on platform."""
        if sys.platform == "win32":
            # Windows: show all drives
            self._model.setRootPath("")
            self.setRootIndex(self._model.index(""))
        else:
            # macOS/Linux: start from root, but expand to home
            self._model.setRootPath("/")
            self.setRootIndex(self._model.index("/"))

            # Expand to home directory
            home = Path.home()
            self._expand_to_path(home)

    def _expand_to_path(self, path: Path):
        """Expand tree to show given path."""
        parts = path.parts
        current = Path(parts[0])

        for part in parts[1:]:
            current = current / part
            index = self._model.index(str(current))
            if index.isValid():
                self.expand(index)

    def _on_clicked(self, index: QModelIndex):
        """Handle item click."""
        path = Path(self._model.filePath(index))
        self.folder_selected.emit(path)

    def select_path(self, path: Path):
        """Select and scroll to path."""
        index = self._model.index(str(path))
        if index.isValid():
            self.setCurrentIndex(index)
            self.scrollTo(index)
            self._expand_to_path(path)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag enter - accept file drops."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        """Handle drag move - highlight target folder."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop - copy/move files to target folder."""
        if event.mimeData().hasUrls():
            # Get drop target folder
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                target_path = Path(self._model.filePath(index))
                if target_path.is_dir():
                    urls = event.mimeData().urls()
                    paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
                    if paths:
                        self.files_dropped.emit(paths, target_path)
                        event.acceptProposedAction()
                        return
        super().dropEvent(event)
