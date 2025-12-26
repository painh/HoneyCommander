"""File list view - center panel."""

from __future__ import annotations

import sys
import subprocess
import zipfile
from pathlib import Path
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    Qt,
    Signal,
    QDir,
    QModelIndex,
    QSize,
    QPoint,
    QTimer,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListView,
    QFileSystemModel,
    QAbstractItemView,
    QMenu,
    QInputDialog,
    QMessageBox,
    QApplication,
    QStackedWidget,
    QHeaderView,
    QLabel,
)
from PySide6.QtGui import QColor, QBrush

from commander.views.file_list.drop_views import DropEnabledTreeView, DropEnabledListView
from commander.views.file_list.thumbnail_delegate import ThumbnailDelegate
from commander.utils.settings import Settings
from commander.utils.themes import get_file_color

if TYPE_CHECKING:
    pass


class ColoredFileSystemModel(QFileSystemModel):
    """QFileSystemModel with theme-based file type colors."""

    def __init__(self, parent=None):
        super().__init__(parent)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Override data to provide custom foreground colors."""
        if role == Qt.ItemDataRole.ForegroundRole:
            file_path = Path(self.filePath(index))
            color_hex = get_file_color(file_path)
            if color_hex:
                return QBrush(QColor(color_hex))

        return super().data(index, role)


class ViewMode(Enum):
    """View modes for the file list."""

    LIST = "list"
    ICONS = "icons"
    THUMBNAILS = "thumbnails"


class FileListView(QWidget):
    """Center panel file list view with multiple view modes."""

    item_selected = Signal(Path)
    item_activated = Signal(Path)
    request_compress = Signal(list)
    request_terminal = Signal(Path)
    request_new_window = Signal(Path)  # Request to open folder in new window

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._model = ColoredFileSystemModel()
        self._model.setFilter(
            QDir.Filter.AllEntries
            | QDir.Filter.NoDotAndDotDot
            | QDir.Filter.Hidden
            | QDir.Filter.System
        )

        self._view_mode = ViewMode.LIST
        self._current_path: Path | None = None

        # Fuzzy search
        self._settings = Settings()
        self._search_text = ""
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(self._settings.load_fuzzy_search_timeout())
        self._search_timer.timeout.connect(self._clear_search)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the stacked widget with different views."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Set focus policy for the container
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        # Tree view for list mode (with columns)
        self._tree_view = DropEnabledTreeView()
        self._tree_view.setModel(self._model)
        self._tree_view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._tree_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree_view.setDragEnabled(True)
        self._tree_view.setDropIndicatorShown(True)
        self._tree_view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._tree_view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree_view.customContextMenuRequested.connect(self._show_context_menu)
        self._tree_view.clicked.connect(self._on_clicked)
        self._tree_view.doubleClicked.connect(self._on_double_clicked)
        self._tree_view.setRootIsDecorated(False)  # Don't show expand arrows
        self._tree_view.setSortingEnabled(True)
        self._tree_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._tree_view.files_dropped.connect(self._on_files_dropped)

        # Configure header
        header = self._tree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Size
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Date

        self._stack.addWidget(self._tree_view)

        # List view for icons/thumbnails mode
        self._list_view = DropEnabledListView()
        self._list_view.setModel(self._model)
        self._list_view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list_view.setDragEnabled(True)
        self._list_view.setDropIndicatorShown(True)
        self._list_view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._list_view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_view.customContextMenuRequested.connect(self._show_context_menu)
        self._list_view.clicked.connect(self._on_clicked)
        self._list_view.doubleClicked.connect(self._on_double_clicked)
        self._list_view.files_dropped.connect(self._on_files_dropped)

        # Thumbnail delegate
        self._thumbnail_delegate = ThumbnailDelegate(self._list_view)
        self._default_delegate = self._list_view.itemDelegate()

        self._stack.addWidget(self._list_view)

        # Default: list mode (tree view)
        self._stack.setCurrentWidget(self._tree_view)

        # Search overlay (hidden by default)
        self._search_label = QLabel(self)
        self._search_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 120, 212, 0.9);
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        self._search_label.hide()
        self._search_label.raise_()  # Ensure it's on top

        # Install event filter to capture key events from views
        self._tree_view.installEventFilter(self)
        self._list_view.installEventFilter(self)

    def _current_view(self) -> QAbstractItemView:
        """Get the current active view."""
        widget = self._stack.currentWidget()
        # Both DropEnabledTreeView and DropEnabledListView are QAbstractItemView subclasses
        assert isinstance(widget, QAbstractItemView)
        return widget

    def focusInEvent(self, event) -> None:
        """Forward focus to the current view."""
        super().focusInEvent(event)
        self._current_view().setFocus()
        self._update_focus_style()

    def focusOutEvent(self, event) -> None:
        """Handle focus out."""
        super().focusOutEvent(event)
        self._update_focus_style()

    def _update_focus_style(self) -> None:
        """Update border style based on focus and theme."""
        from commander.utils.themes import get_theme_manager

        theme = get_theme_manager().get_current_theme()

        # Check if any child view has focus
        has_focus = self.hasFocus() or self._tree_view.hasFocus() or self._list_view.hasFocus()

        # Only apply focus border for retro theme
        # Use dark cyan/teal like classic MDIR style
        if theme.name == "retro" and has_focus:
            self.setStyleSheet("FileListView { border: 2px solid #008080; }")
        else:
            self.setStyleSheet("")

    def set_root_path(self, path: Path) -> None:
        """Set the directory to display."""
        self._current_path = path
        self._model.setRootPath(str(path))

        root_index = self._model.index(str(path))
        self._tree_view.setRootIndex(root_index)
        self._list_view.setRootIndex(root_index)

        # Update drop target path
        self._tree_view.set_current_path(path)
        self._list_view.set_current_path(path)

        # Reconnect selection changed signals
        self._connect_selection_signals()

    def _connect_selection_signals(self) -> None:
        """Connect selection changed signals for both views."""
        # Tree view - disconnect then reconnect
        tree_selection_model = self._tree_view.selectionModel()
        try:
            tree_selection_model.selectionChanged.disconnect(self._on_selection_changed)
        except (RuntimeError, TypeError):
            pass
        tree_selection_model.selectionChanged.connect(self._on_selection_changed)

        # List view - disconnect then reconnect
        list_selection_model = self._list_view.selectionModel()
        try:
            list_selection_model.selectionChanged.disconnect(self._on_selection_changed)
        except (RuntimeError, TypeError):
            pass
        list_selection_model.selectionChanged.connect(self._on_selection_changed)

    def set_view_mode(self, mode: str) -> None:
        """Change view mode (list, icons, thumbnails)."""
        self._view_mode = ViewMode(mode)

        if self._view_mode == ViewMode.LIST:
            # Use tree view for detailed list with columns
            self._stack.setCurrentWidget(self._tree_view)
            self._tree_view.setIconSize(QSize(16, 16))
        elif self._view_mode == ViewMode.ICONS:
            # Use list view in icon mode
            self._stack.setCurrentWidget(self._list_view)
            self._list_view.setViewMode(QListView.ViewMode.IconMode)
            self._list_view.setGridSize(QSize(100, 80))
            self._list_view.setIconSize(QSize(48, 48))
            self._list_view.setSpacing(10)
            self._list_view.setWordWrap(True)
            self._list_view.setItemDelegate(self._default_delegate)
        elif self._view_mode == ViewMode.THUMBNAILS:
            # Use list view in thumbnail mode
            self._stack.setCurrentWidget(self._list_view)
            self._list_view.setViewMode(QListView.ViewMode.IconMode)
            self._list_view.setGridSize(QSize(150, 150))
            self._list_view.setIconSize(QSize(128, 128))
            self._list_view.setSpacing(10)
            self._list_view.setWordWrap(True)
            self._list_view.setItemDelegate(self._thumbnail_delegate)

    def _on_clicked(self, index: QModelIndex) -> None:
        """Handle single click - select and preview."""
        path = Path(self._model.filePath(index))
        self.item_selected.emit(path)

    def _on_selection_changed(self, selected, deselected) -> None:
        """Handle selection change (keyboard navigation)."""
        view = self._current_view()
        indexes = view.selectionModel().selectedIndexes()
        if indexes:
            # Get the first column index (name)
            for idx in indexes:
                if idx.column() == 0:
                    path = Path(self._model.filePath(idx))
                    self.item_selected.emit(path)
                    break

    def _on_double_clicked(self, index: QModelIndex) -> None:
        """Handle double click - activate (open/navigate)."""
        path = Path(self._model.filePath(index))
        self.item_activated.emit(path)

    def get_selected_paths(self) -> list[Path]:
        """Get list of selected file paths."""
        paths: list[Path] = []
        view = self._current_view()
        for index in view.selectionModel().selectedIndexes():
            if index.column() == 0:  # Only count name column
                path = Path(self._model.filePath(index))
                if path not in paths:
                    paths.append(path)
        return paths

    def start_rename(self) -> None:
        """Start renaming selected item."""
        view = self._current_view()
        indexes = view.selectionModel().selectedIndexes()
        for idx in indexes:
            if idx.column() == 0:
                view.edit(idx)
                break

    def selectionModel(self):
        """Get selection model of current view (for compatibility)."""
        return self._current_view().selectionModel()

    def selectedIndexes(self):
        """Get selected indexes of current view (for compatibility)."""
        return self._current_view().selectionModel().selectedIndexes()

    # === Context Menu ===

    def _show_context_menu(self, pos: QPoint) -> None:
        """Show context menu with custom options."""
        from commander.utils.custom_commands import get_custom_commands_manager

        selected_paths = self.get_selected_paths()

        menu = QMenu(self)

        # Open with default app
        if selected_paths:
            open_action = menu.addAction("Open")
            open_action.triggered.connect(lambda: self._open_with_default(selected_paths[0]))

            # Open in New Window (for folders)
            if len(selected_paths) == 1 and selected_paths[0].is_dir():
                new_window_action = menu.addAction("Open in New Window")
                new_window_action.triggered.connect(
                    lambda: self.request_new_window.emit(selected_paths[0])
                )

            # Custom commands submenu
            if len(selected_paths) == 1:
                custom_cmds = get_custom_commands_manager().get_commands_for_path(selected_paths[0])
                if custom_cmds:
                    menu.addSeparator()
                    for cmd in custom_cmds:
                        # Show shortcut in menu name like "Open in Image Viewer(3)"
                        name = cmd.name
                        if cmd.shortcut:
                            name = f"{cmd.name}({cmd.shortcut})"
                        action = menu.addAction(name)
                        if cmd.shortcut:
                            action.setShortcut(cmd.shortcut)
                        action.triggered.connect(
                            lambda checked, c=cmd, p=selected_paths[0]: self._run_custom_command(
                                c, p
                            )
                        )

            # Open With submenu (macOS only for now)
            if sys.platform == "darwin" and len(selected_paths) == 1:
                open_with_menu = menu.addMenu("Open With")
                self._populate_open_with_menu(open_with_menu, selected_paths[0])

            if len(selected_paths) == 1:
                menu.addSeparator()

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

        # Show in Finder/Explorer
        if sys.platform == "darwin":
            reveal_action = menu.addAction("Reveal in Finder")
        elif sys.platform == "win32":
            reveal_action = menu.addAction("Open in Explorer")
        else:
            reveal_action = menu.addAction("Open in File Manager")

        reveal_path = selected_paths[0] if selected_paths else self._current_path
        if reveal_path:
            reveal_action.triggered.connect(lambda: self._reveal_in_finder(reveal_path))

        view = self._current_view()
        menu.exec(view.mapToGlobal(pos))

    def _run_custom_command(self, cmd, path: Path) -> None:
        """Run a custom command."""
        from commander.utils.custom_commands import get_custom_commands_manager

        mgr = get_custom_commands_manager()
        if mgr.is_builtin_command(cmd):
            # Handle built-in commands
            if cmd.command == "__builtin__:image_viewer":
                self._open_builtin_image_viewer(path)
            elif cmd.command == "__builtin__:extract":
                self._extract_archive(path)
        else:
            cmd.execute(path)

    def _extract_archive(self, path: Path) -> None:
        """Extract archive to same directory."""
        from commander.core.archive_handler import ArchiveManager

        if not path.is_file():
            return

        # Extract to directory with same name as archive (without extension)
        extract_dir = path.parent / path.stem

        try:
            ArchiveManager.extract(path, extract_dir)
            # Refresh view
            if self._current_path:
                self.set_root_path(self._current_path)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Extract Error",
                f"Failed to extract archive:\n{e}",
            )

    def _open_builtin_image_viewer(self, path: Path) -> None:
        """Open built-in image viewer."""
        from commander.views.viewer import FullscreenImageViewer
        from commander.core.image_loader import ALL_IMAGE_FORMATS
        from commander.core.archive_handler import ArchiveManager

        if path.is_dir():
            images = self._collect_images_from_dir(path, ALL_IMAGE_FORMATS)
            if images:
                path = images[0]
            else:
                return  # No images in directory
        elif ArchiveManager.is_archive(path):
            # Open archive in image viewer - viewer will handle extracting images
            if not hasattr(self, "_viewer") or self._viewer is None:
                self._viewer = FullscreenImageViewer(self.window())
            self._viewer.show_archive(path)
            return
        else:
            # Get all images in same directory
            parent = path.parent
            images = sorted([p for p in parent.iterdir() if p.suffix.lower() in ALL_IMAGE_FORMATS])

        if not hasattr(self, "_viewer") or self._viewer is None:
            self._viewer = FullscreenImageViewer(self.window())

        self._viewer.show_image(path, images)

    def _collect_images_from_dir(self, path: Path, formats: set) -> list[Path]:
        """Collect images from directory, optionally including subdirectories."""
        from commander.utils.i18n import tr

        # Check if there are subdirectories with images
        subdirs = [p for p in path.iterdir() if p.is_dir()]
        has_subdirs_with_images = False

        for subdir in subdirs:
            try:
                if any(p.suffix.lower() in formats for p in subdir.iterdir() if p.is_file()):
                    has_subdirs_with_images = True
                    break
            except PermissionError:
                continue

        include_subdirs = False
        if has_subdirs_with_images:
            reply = QMessageBox.question(
                self,
                tr("image_viewer_subfolders_title"),
                tr("image_viewer_subfolders_question"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            include_subdirs = reply == QMessageBox.StandardButton.Yes

        if include_subdirs:
            # Recursively collect all images
            images = []
            for p in sorted(path.rglob("*")):
                if p.is_file() and p.suffix.lower() in formats:
                    images.append(p)
            return images
        else:
            # Only current directory
            return sorted(
                [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in formats]
            )

    # === File Operations ===

    def _open_with_default(self, path: Path) -> None:
        """Open file with default application."""
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        elif sys.platform == "win32":
            import os

            os.startfile(str(path))
        else:
            subprocess.run(["xdg-open", str(path)])

    def _copy_files(self, paths: list[Path]) -> None:
        """Copy files to clipboard."""
        from commander.core.file_operations import FileOperations

        ops = FileOperations()
        ops.copy_to_clipboard(paths)

    def _cut_files(self, paths: list[Path]) -> None:
        """Cut files to clipboard."""
        from commander.core.file_operations import FileOperations

        ops = FileOperations()
        ops.cut_to_clipboard(paths)

    def _paste_files(self) -> None:
        """Paste files from clipboard."""
        from commander.core.file_operations import FileOperations
        from commander.widgets.progress_dialog import ProgressDialog

        if self._current_path is None:
            return

        ops = FileOperations()
        if not ops.has_clipboard():
            return

        # Use progress dialog for paste operation
        dialog = ProgressDialog("paste", [], self._current_path, self)
        dialog.exec()
        self.set_root_path(self._current_path)

    def _delete_files(self, paths: list[Path]) -> None:
        """Delete files."""
        from commander.core.file_operations import FileOperations

        if self._current_path is None:
            return

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

    def _create_new_folder(self) -> None:
        """Create new folder."""
        if self._current_path is None:
            return

        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            new_path = self._current_path / name
            try:
                new_path.mkdir()
                self.set_root_path(self._current_path)
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Cannot create folder: {e}")

    def _create_new_file(self) -> None:
        """Create a new empty file."""
        if self._current_path is None:
            return

        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if ok and name:
            new_path = self._current_path / name
            try:
                new_path.touch()
                self.set_root_path(self._current_path)
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Cannot create file: {e}")

    def _compress_files(self, paths: list[Path]) -> None:
        """Compress selected files to ZIP."""
        if self._current_path is None:
            return

        # Ask for zip file name
        default_name = paths[0].stem if len(paths) == 1 else "archive"
        name, ok = QInputDialog.getText(self, "Compress", "Archive name:", text=default_name)
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

    def _open_terminal(self) -> None:
        """Open terminal at current path."""
        path = self._current_path
        if path is None:
            return

        if sys.platform == "darwin":
            script = f'tell app "Terminal" to do script "cd {path}"'
            subprocess.run(["osascript", "-e", script])
        elif sys.platform == "win32":
            subprocess.Popen(
                ["powershell", "-NoExit", "-Command", f"cd '{path}'"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            for term in ["gnome-terminal", "konsole", "xterm"]:
                try:
                    subprocess.Popen([term, "--working-directory", str(path)])
                    break
                except FileNotFoundError:
                    continue

    def _reveal_in_finder(self, path: Path) -> None:
        """Reveal file/folder in Finder/Explorer."""
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(path)])
        else:
            subprocess.run(["xdg-open", str(path.parent)])

    def _copy_path(self, paths: list[Path]) -> None:
        """Copy file paths to clipboard."""
        clipboard = QApplication.clipboard()
        if len(paths) == 1:
            clipboard.setText(str(paths[0]))
        else:
            clipboard.setText("\n".join(str(p) for p in paths))

    def _show_info(self, path: Path) -> None:
        """Show file/folder info dialog."""
        from commander.widgets.info_dialog import InfoDialog

        dialog = InfoDialog(path, self)
        dialog.exec()

    def _quick_look(self, path: Path) -> None:
        """Open Quick Look preview (macOS only)."""
        if sys.platform == "darwin":
            subprocess.run(
                ["qlmanage", "-p", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

    def _populate_open_with_menu(self, menu: QMenu, path: Path) -> None:
        """Populate Open With submenu with available apps."""
        if sys.platform == "darwin":
            try:
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

    def _open_with_other(self, path: Path) -> None:
        """Open file with user-selected application."""
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Finder", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["rundll32", "shell32.dll,OpenAs_RunDLL", str(path)])

    def _on_files_dropped(self, paths: list[Path], destination: Path) -> None:
        """Handle files dropped from external app (e.g., Finder)."""
        from commander.widgets.progress_dialog import ProgressDialog

        if self._current_path is None:
            return

        # Filter out files that are already in the destination
        paths_to_copy = [p for p in paths if p.parent != destination]
        if not paths_to_copy:
            return

        # Ask user: Copy or Move?
        reply = QMessageBox.question(
            self,
            "Drop Files",
            f"Copy {len(paths_to_copy)} item(s) to this folder?\n\n"
            f"Click 'Yes' to copy, 'No' to move.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Cancel:
            return

        if reply == QMessageBox.StandardButton.Yes:
            # Copy
            dialog = ProgressDialog("copy", paths_to_copy, destination, self)
            dialog.exec()
        else:
            # Move
            dialog = ProgressDialog("move", paths_to_copy, destination, self)
            dialog.exec()

        self.set_root_path(self._current_path)

    # === Fuzzy Search ===

    def eventFilter(self, obj, event) -> bool:
        """Filter key events from child views for fuzzy search."""
        # Handle focus events from child views
        if event.type() in (event.Type.FocusIn, event.Type.FocusOut):
            self._update_focus_style()

        if event.type() == event.Type.KeyPress:
            key = event.key()
            text = event.text()

            # Escape clears search
            if key == Qt.Key.Key_Escape and self._search_text:
                self._clear_search()
                return True

            # Backspace removes last character from search
            if key == Qt.Key.Key_Backspace and self._search_text:
                self._search_text = self._search_text[:-1]
                if self._search_text:
                    self._do_fuzzy_search()
                else:
                    self._clear_search()
                return True

            # Only handle printable characters (no modifiers except shift)
            modifiers = event.modifiers()
            has_ctrl_or_meta = modifiers & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
            )

            if text and text.isprintable() and not has_ctrl_or_meta:
                self._search_text += text.lower()
                self._do_fuzzy_search()
                self._search_timer.start()
                return True

        return super().eventFilter(obj, event)

    def _do_fuzzy_search(self) -> None:
        """Perform fuzzy search and select matching file."""
        if not self._search_text or not self._current_path:
            return

        # Show search overlay
        self._search_label.setText(f"Search: {self._search_text}")
        self._search_label.adjustSize()
        self._search_label.move(10, self.height() - self._search_label.height() - 10)
        self._search_label.show()

        # Get all items in current directory
        view = self._current_view()
        model = self._model
        root_index = view.rootIndex()

        best_match: QModelIndex | None = None
        best_score = -1

        for row in range(model.rowCount(root_index)):
            index = model.index(row, 0, root_index)
            filename = model.fileName(index).lower()

            # Calculate fuzzy match score
            score = self._fuzzy_score(self._search_text, filename)
            if score > best_score:
                best_score = score
                best_match = index

        # Select best match
        if best_match is not None and best_score > 0:
            view.setCurrentIndex(best_match)
            view.scrollTo(best_match)
            self._on_clicked(best_match)

    def _fuzzy_score(self, pattern: str, text: str) -> int:
        """Calculate fuzzy match score. Higher is better."""
        if not pattern:
            return 0

        # Exact prefix match gets highest score
        if text.startswith(pattern):
            return 1000 + len(pattern)

        # Check if all characters appear in order
        pattern_idx = 0
        score = 0
        consecutive = 0

        for i, char in enumerate(text):
            if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
                pattern_idx += 1
                consecutive += 1
                # Bonus for consecutive matches
                score += consecutive * 10
                # Bonus for match at start
                if i == 0:
                    score += 50
            else:
                consecutive = 0

        # All pattern characters must be found
        if pattern_idx < len(pattern):
            return 0

        return score

    def _clear_search(self) -> None:
        """Clear fuzzy search."""
        self._search_text = ""
        self._search_label.hide()
        self._search_timer.stop()
