"""File list view - center panel."""

import sys
import subprocess
from pathlib import Path
from enum import Enum

from PySide6.QtCore import Qt, Signal, QDir, QModelIndex, QSize, QMimeData, QUrl, QPoint
from PySide6.QtWidgets import (
    QListView,
    QFileSystemModel,
    QAbstractItemView,
    QMenu,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtGui import QDrag, QAction, QCursor


class ViewMode(Enum):
    LIST = "list"
    ICONS = "icons"
    THUMBNAILS = "thumbnails"


class FileListView(QListView):
    """Center panel file list view."""

    item_selected = Signal(Path)
    item_activated = Signal(Path)
    request_compress = Signal(list)  # Signal to request compression
    request_terminal = Signal(Path)  # Signal to open terminal at path

    def __init__(self, parent=None):
        super().__init__(parent)

        self._model = QFileSystemModel()
        # Show hidden files and all entries
        self._model.setFilter(
            QDir.Filter.AllEntries
            | QDir.Filter.NoDotAndDotDot
            | QDir.Filter.Hidden
            | QDir.Filter.System
        )
        self.setModel(self._model)

        self._view_mode = ViewMode.LIST
        self._current_path: Path | None = None

        # Selection
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Drag and drop
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

        # Context menu - use custom menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Signals
        self.clicked.connect(self._on_clicked)
        self.doubleClicked.connect(self._on_double_clicked)

        # Selection change (for keyboard navigation)
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Default view mode
        self.set_view_mode("list")

    def set_root_path(self, path: Path):
        """Set the directory to display."""
        self._current_path = path
        self._model.setRootPath(str(path))
        self.setRootIndex(self._model.index(str(path)))

        # Reconnect selection changed signal (model change can disconnect it)
        try:
            self.selectionModel().selectionChanged.disconnect(self._on_selection_changed)
        except (RuntimeError, TypeError):
            pass
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def set_view_mode(self, mode: str):
        """Change view mode (list, icons, thumbnails)."""
        self._view_mode = ViewMode(mode)

        if self._view_mode == ViewMode.LIST:
            self.setViewMode(QListView.ViewMode.ListMode)
            self.setGridSize(QSize())
            self.setIconSize(QSize(16, 16))
            self.setSpacing(0)
        elif self._view_mode == ViewMode.ICONS:
            self.setViewMode(QListView.ViewMode.IconMode)
            self.setGridSize(QSize(100, 80))
            self.setIconSize(QSize(48, 48))
            self.setSpacing(10)
            self.setWordWrap(True)
        elif self._view_mode == ViewMode.THUMBNAILS:
            self.setViewMode(QListView.ViewMode.IconMode)
            self.setGridSize(QSize(150, 150))
            self.setIconSize(QSize(128, 128))
            self.setSpacing(10)
            self.setWordWrap(True)

    def _on_clicked(self, index: QModelIndex):
        """Handle single click - select and preview."""
        path = Path(self._model.filePath(index))
        self.item_selected.emit(path)

    def _on_selection_changed(self, selected, deselected):
        """Handle selection change (keyboard navigation)."""
        indexes = self.selectedIndexes()
        if indexes:
            path = Path(self._model.filePath(indexes[0]))
            self.item_selected.emit(path)

    def _on_double_clicked(self, index: QModelIndex):
        """Handle double click - activate (open/navigate)."""
        path = Path(self._model.filePath(index))
        self.item_activated.emit(path)

    def get_selected_paths(self) -> list[Path]:
        """Get list of selected file paths."""
        paths = []
        for index in self.selectedIndexes():
            path = Path(self._model.filePath(index))
            if path not in paths:
                paths.append(path)
        return paths

    def start_rename(self):
        """Start renaming selected item."""
        indexes = self.selectedIndexes()
        if indexes:
            self.edit(indexes[0])

    def _show_context_menu(self, pos: QPoint):
        """Show context menu with custom options."""
        selected_paths = self.get_selected_paths()

        menu = QMenu(self)

        # Open with default app
        if selected_paths:
            open_action = menu.addAction("Open")
            open_action.triggered.connect(lambda: self._open_with_default(selected_paths[0]))

            # Open With submenu (macOS only for now)
            if sys.platform == "darwin" and len(selected_paths) == 1:
                open_with_menu = menu.addMenu("Open With")
                self._populate_open_with_menu(open_with_menu, selected_paths[0])

            if len(selected_paths) == 1:
                # Rename (F2)
                rename_action = menu.addAction("Rename")
                rename_action.setShortcut("F2")
                rename_action.triggered.connect(self.start_rename)

                # Get Info
                info_action = menu.addAction("Get Info")
                info_action.triggered.connect(lambda: self._show_info(selected_paths[0]))

            menu.addSeparator()

            # Copy/Cut/Delete
            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(lambda: self._copy_files(selected_paths))

            cut_action = menu.addAction("Cut")
            cut_action.triggered.connect(lambda: self._cut_files(selected_paths))

            # Copy Path
            copy_path_action = menu.addAction("Copy Path")
            copy_path_action.triggered.connect(lambda: self._copy_path(selected_paths))

            menu.addSeparator()

            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self._delete_files(selected_paths))

            menu.addSeparator()

            # Compress option
            if len(selected_paths) >= 1:
                compress_action = menu.addAction("Compress to ZIP...")
                compress_action.triggered.connect(lambda: self._compress_files(selected_paths))

            # Quick Look (macOS)
            if sys.platform == "darwin" and len(selected_paths) == 1:
                quicklook_action = menu.addAction("Quick Look")
                quicklook_action.triggered.connect(lambda: self._quick_look(selected_paths[0]))

        menu.addSeparator()

        # Paste (always available)
        paste_action = menu.addAction("Paste")
        paste_action.triggered.connect(self._paste_files)

        menu.addSeparator()

        # New folder
        new_folder_action = menu.addAction("New Folder")
        new_folder_action.triggered.connect(self._create_new_folder)

        # New file
        new_file_action = menu.addAction("New File")
        new_file_action.triggered.connect(self._create_new_file)

        menu.addSeparator()

        # Open terminal here
        if sys.platform == "darwin":
            terminal_action = menu.addAction("Open Terminal Here")
        elif sys.platform == "win32":
            terminal_action = menu.addAction("Open PowerShell Here")
        else:
            terminal_action = menu.addAction("Open Terminal Here")
        terminal_action.triggered.connect(self._open_terminal)

        # Show in Finder/Explorer
        if sys.platform == "darwin":
            reveal_action = menu.addAction("Reveal in Finder")
        elif sys.platform == "win32":
            reveal_action = menu.addAction("Open in Explorer")
        else:
            reveal_action = menu.addAction("Open in File Manager")
        reveal_action.triggered.connect(
            lambda: self._reveal_in_finder(selected_paths[0] if selected_paths else self._current_path)
        )

        menu.exec(self.mapToGlobal(pos))

    def _open_with_default(self, path: Path):
        """Open file with default application."""
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        elif sys.platform == "win32":
            import os
            os.startfile(str(path))
        else:
            subprocess.run(["xdg-open", str(path)])

    def _copy_files(self, paths: list[Path]):
        """Copy files to clipboard."""
        from commander.core.file_operations import FileOperations
        ops = FileOperations()
        ops.copy_to_clipboard(paths)

    def _cut_files(self, paths: list[Path]):
        """Cut files to clipboard."""
        from commander.core.file_operations import FileOperations
        ops = FileOperations()
        ops.cut_to_clipboard(paths)

    def _paste_files(self):
        """Paste files from clipboard."""
        from commander.core.file_operations import FileOperations
        from commander.widgets.progress_dialog import ProgressDialog

        ops = FileOperations()
        if not ops.has_clipboard():
            return

        # Use progress dialog for paste operation
        dialog = ProgressDialog("paste", [], self._current_path, self)
        dialog.exec()
        self.set_root_path(self._current_path)

    def _delete_files(self, paths: list[Path]):
        """Delete files."""
        from commander.core.file_operations import FileOperations
        reply = QMessageBox.question(
            self,
            "Delete",
            f"Move {len(paths)} item(s) to Trash?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ops = FileOperations()
            ops.delete(paths)
            self.set_root_path(self._current_path)

    def _create_new_folder(self):
        """Create new folder."""
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            new_path = self._current_path / name
            try:
                new_path.mkdir()
                self.set_root_path(self._current_path)
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Cannot create folder: {e}")

    def _compress_files(self, paths: list[Path]):
        """Compress selected files to ZIP."""
        import zipfile

        # Ask for zip file name
        default_name = paths[0].stem if len(paths) == 1 else "archive"
        name, ok = QInputDialog.getText(
            self, "Compress", "Archive name:", text=default_name
        )
        if not ok or not name:
            return

        zip_path = self._current_path / f"{name}.zip"

        # Check if exists
        if zip_path.exists():
            reply = QMessageBox.question(
                self,
                "Overwrite?",
                f"{zip_path.name} already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for path in paths:
                    if path.is_file():
                        zf.write(path, path.name)
                    elif path.is_dir():
                        for file in path.rglob("*"):
                            if file.is_file():
                                arcname = path.name / file.relative_to(path)
                                zf.write(file, arcname)

            self.set_root_path(self._current_path)
            QMessageBox.information(self, "Success", f"Created {zip_path.name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Compression failed: {e}")

    def _open_terminal(self):
        """Open terminal at current path."""
        path = self._current_path
        if sys.platform == "darwin":
            # macOS: open Terminal.app
            script = f'tell app "Terminal" to do script "cd {path}"'
            subprocess.run(["osascript", "-e", script])
        elif sys.platform == "win32":
            # Windows: open PowerShell
            subprocess.Popen(
                ["powershell", "-NoExit", "-Command", f"cd '{path}'"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            # Linux: try common terminals
            for term in ["gnome-terminal", "konsole", "xterm"]:
                try:
                    subprocess.Popen([term, "--working-directory", str(path)])
                    break
                except FileNotFoundError:
                    continue

    def _reveal_in_finder(self, path: Path):
        """Reveal file/folder in Finder/Explorer."""
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(path)])
        else:
            subprocess.run(["xdg-open", str(path.parent)])

    def _copy_path(self, paths: list[Path]):
        """Copy file paths to clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if len(paths) == 1:
            clipboard.setText(str(paths[0]))
        else:
            clipboard.setText("\n".join(str(p) for p in paths))

    def _show_info(self, path: Path):
        """Show file/folder info dialog."""
        from commander.widgets.info_dialog import InfoDialog
        dialog = InfoDialog(path, self)
        dialog.exec()

    def _quick_look(self, path: Path):
        """Open Quick Look preview (macOS only)."""
        if sys.platform == "darwin":
            subprocess.run(["qlmanage", "-p", str(path)],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

    def _populate_open_with_menu(self, menu: QMenu, path: Path):
        """Populate Open With submenu with available apps."""
        if sys.platform == "darwin":
            # Get default apps for this file type
            try:
                import plistlib
                result = subprocess.run(
                    ["mdls", "-name", "kMDItemContentType", "-raw", str(path)],
                    capture_output=True, text=True
                )
                content_type = result.stdout.strip()

                # Get apps that can open this type
                result = subprocess.run(
                    ["lsappinfo", "find", "canopen=" + str(path)],
                    capture_output=True, text=True
                )

                # Add common apps as fallback
                common_apps = [
                    ("TextEdit", "/System/Applications/TextEdit.app"),
                    ("Preview", "/System/Applications/Preview.app"),
                    ("VS Code", "/Applications/Visual Studio Code.app"),
                ]

                for name, app_path in common_apps:
                    if Path(app_path).exists():
                        action = menu.addAction(name)
                        action.triggered.connect(
                            lambda checked, p=app_path: subprocess.run(["open", "-a", p, str(path)])
                        )

                menu.addSeparator()
                other_action = menu.addAction("Other...")
                other_action.triggered.connect(lambda: self._open_with_other(path))

            except Exception:
                other_action = menu.addAction("Choose Application...")
                other_action.triggered.connect(lambda: self._open_with_other(path))
        else:
            other_action = menu.addAction("Choose Application...")
            other_action.triggered.connect(lambda: self._open_with_other(path))

    def _open_with_other(self, path: Path):
        """Open file with user-selected application."""
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Finder", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["rundll32", "shell32.dll,OpenAs_RunDLL", str(path)])

    def _create_new_file(self):
        """Create a new empty file."""
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if ok and name:
            new_path = self._current_path / name
            try:
                new_path.touch()
                self.set_root_path(self._current_path)
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Cannot create file: {e}")

    def dragEnterEvent(self, event):
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """Handle drag move."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """Handle drop."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            paths = [Path(url.toLocalFile()) for url in urls]

            # Determine drop target
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                target = Path(self._model.filePath(index))
                if target.is_dir():
                    dest = target
                else:
                    dest = self._current_path
            else:
                dest = self._current_path

            from commander.core.file_operations import FileOperations

            ops = FileOperations()
            if event.dropAction() == Qt.DropAction.MoveAction:
                ops.move(paths, dest)
            else:
                ops.copy(paths, dest)

            self.set_root_path(self._current_path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def startDrag(self, supportedActions):
        """Start drag operation."""
        paths = self.get_selected_paths()
        if not paths:
            return

        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile(str(p)) for p in paths]
        mime_data.setUrls(urls)

        drag = QDrag(self)
        drag.setMimeData(mime_data)

        index = self.selectedIndexes()[0]
        icon = self._model.fileIcon(index)
        drag.setPixmap(icon.pixmap(32, 32))

        drag.exec(supportedActions)
