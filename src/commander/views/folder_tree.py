"""Folder tree view - left panel."""

import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QDir, QModelIndex, QPoint
from PySide6.QtWidgets import (
    QTreeView,
    QFileSystemModel,
    QAbstractItemView,
    QMenu,
    QApplication,
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent


class FolderTreeView(QTreeView):
    """Left panel folder tree view with drag and drop support."""

    folder_selected = Signal(Path)
    files_dropped = Signal(list, Path)  # dropped files, destination folder
    request_new_window = Signal(Path)  # Request to open folder in new window

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

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

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

    def _show_context_menu(self, pos: QPoint) -> None:
        """Show context menu for folder."""
        from commander.utils.custom_commands import get_custom_commands_manager

        index = self.indexAt(pos)
        if not index.isValid():
            return

        path = Path(self._model.filePath(index))
        if not path.is_dir():
            return

        menu = QMenu(self)

        # Open
        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self.folder_selected.emit(path))

        # Open in New Window
        new_window_action = menu.addAction("Open in New Window")
        new_window_action.triggered.connect(lambda: self.request_new_window.emit(path))

        # Custom commands
        custom_cmds = get_custom_commands_manager().get_commands_for_path(path)
        if custom_cmds:
            menu.addSeparator()
            for cmd in custom_cmds:
                action = menu.addAction(cmd.name)
                action.triggered.connect(
                    lambda checked, c=cmd, p=path: self._run_custom_command(c, p)
                )

        menu.addSeparator()

        # Copy Path
        copy_path_action = menu.addAction("Copy Path")
        copy_path_action.triggered.connect(lambda: self._copy_path(path))

        menu.addSeparator()

        # Show in Finder/Explorer
        if sys.platform == "darwin":
            reveal_action = menu.addAction("Reveal in Finder")
        elif sys.platform == "win32":
            reveal_action = menu.addAction("Open in Explorer")
        else:
            reveal_action = menu.addAction("Open in File Manager")
        reveal_action.triggered.connect(lambda: self._reveal_in_finder(path))

        menu.exec(self.mapToGlobal(pos))

    def _run_custom_command(self, cmd, path: Path) -> None:
        """Run a custom command."""
        from commander.utils.custom_commands import get_custom_commands_manager

        mgr = get_custom_commands_manager()
        if mgr.is_builtin_command(cmd):
            # Handle built-in commands
            if cmd.command == "__builtin__:image_viewer":
                self._open_builtin_image_viewer(path)
        else:
            cmd.execute(path)

    def _open_builtin_image_viewer(self, path: Path) -> None:
        """Open built-in image viewer for directory."""
        from commander.views.viewer import FullscreenImageViewer
        from commander.core.image_loader import ALL_IMAGE_FORMATS

        # Find first image in directory
        images = sorted([p for p in path.iterdir() if p.suffix.lower() in ALL_IMAGE_FORMATS])
        if not images:
            return

        if not hasattr(self, "_viewer") or self._viewer is None:
            self._viewer = FullscreenImageViewer(self.window())

        self._viewer.show_image(images[0], images)

    def _copy_path(self, path: Path) -> None:
        """Copy path to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(str(path))

    def _open_terminal(self, path: Path) -> None:
        """Open terminal at path."""
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Terminal", str(path)])
        elif sys.platform == "win32":
            subprocess.Popen(["powershell", "-NoExit", "-Command", f"cd '{path}'"])
        else:
            subprocess.Popen(["x-terminal-emulator", "--working-directory", str(path)])

    def _reveal_in_finder(self, path: Path) -> None:
        """Reveal path in system file manager."""
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(path)])
        else:
            subprocess.run(["xdg-open", str(path.parent)])
