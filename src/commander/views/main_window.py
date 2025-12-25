"""Main window with 3-panel layout."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QDir
from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QLineEdit,
    QPushButton,
    QStatusBar,
    QTreeView,
    QListView,
    QLabel,
    QFileSystemModel,
    QAbstractItemView,
    QMenu,
    QInputDialog,
    QDialog,
)
from PySide6.QtGui import QAction, QKeySequence, QIcon, QShortcut

from commander.views.folder_tree import FolderTreeView
from commander.views.file_list import FileListView
from commander.views.preview_panel import PreviewPanel
from commander.widgets.address_bar import AddressBar
from commander.widgets.favorites_panel import FavoritesPanel
from commander.core.file_operations import FileOperations
from commander.core.undo_manager import get_undo_manager
from commander.utils.settings import Settings


class MainWindow(QMainWindow):
    """Main window with explorer-style 3-panel layout."""

    def __init__(self):
        super().__init__()
        self._settings = Settings()
        self._current_path: Path = Path.home()
        self._history: list[Path] = [self._current_path]
        self._history_index: int = 0
        self._file_ops = FileOperations()

        self._setup_toolbar()
        self._setup_ui()
        self._setup_menu()
        self._setup_shortcuts()
        self._connect_signals()
        self._load_settings()

        self.setWindowTitle("Commander")

    def _setup_ui(self):
        """Setup the main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Address bar
        self._address_bar = AddressBar()
        main_layout.addWidget(self._address_bar)

        # 3-panel splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Favorites + Folder tree
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._favorites_panel = FavoritesPanel()
        self._folder_tree = FolderTreeView()

        left_layout.addWidget(self._favorites_panel)
        left_layout.addWidget(self._folder_tree, stretch=1)

        self._file_list = FileListView()
        self._preview_panel = PreviewPanel()

        self._splitter.addWidget(left_panel)
        self._splitter.addWidget(self._file_list)
        self._splitter.addWidget(self._preview_panel)

        # Default sizes (1:3:1 ratio)
        self._splitter.setSizes([200, 600, 200])

        main_layout.addWidget(self._splitter, stretch=1)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        # Navigate to home
        self._navigate_to(self._current_path)

    def _setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        new_folder_action = QAction("New Folder", self)
        new_folder_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        new_folder_action.triggered.connect(self._create_new_folder)
        file_menu.addAction(new_folder_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("Edit")

        # Undo/Redo
        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self._undo)
        self._undo_action.setEnabled(False)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction("Redo", self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.triggered.connect(self._redo)
        self._redo_action.setEnabled(False)
        edit_menu.addAction(self._redo_action)

        edit_menu.addSeparator()

        self._copy_action = QAction("Copy", self)
        self._copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self._copy_action.triggered.connect(self._copy_selected)
        edit_menu.addAction(self._copy_action)

        self._cut_action = QAction("Cut", self)
        self._cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        self._cut_action.triggered.connect(self._cut_selected)
        edit_menu.addAction(self._cut_action)

        self._paste_action = QAction("Paste", self)
        self._paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self._paste_action.triggered.connect(self._paste)
        edit_menu.addAction(self._paste_action)

        edit_menu.addSeparator()

        self._delete_action = QAction("Delete", self)
        self._delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self._delete_action.triggered.connect(self._delete_selected)
        edit_menu.addAction(self._delete_action)

        self._rename_action = QAction("Rename", self)
        self._rename_action.setShortcut(QKeySequence("F2"))
        self._rename_action.triggered.connect(self._rename_selected)
        edit_menu.addAction(self._rename_action)

        # View menu
        view_menu = menubar.addMenu("View")

        self._list_view_action = QAction("List", self)
        self._list_view_action.triggered.connect(lambda: self._file_list.set_view_mode("list"))
        view_menu.addAction(self._list_view_action)

        self._icon_view_action = QAction("Icons", self)
        self._icon_view_action.triggered.connect(lambda: self._file_list.set_view_mode("icons"))
        view_menu.addAction(self._icon_view_action)

        self._thumb_view_action = QAction("Thumbnails", self)
        self._thumb_view_action.triggered.connect(
            lambda: self._file_list.set_view_mode("thumbnails")
        )
        view_menu.addAction(self._thumb_view_action)

    def _setup_toolbar(self):
        """Setup navigation toolbar."""
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._back_btn = QPushButton("<")
        self._back_btn.setFixedWidth(30)
        self._back_btn.clicked.connect(self._go_back)
        toolbar.addWidget(self._back_btn)

        self._forward_btn = QPushButton(">")
        self._forward_btn.setFixedWidth(30)
        self._forward_btn.clicked.connect(self._go_forward)
        toolbar.addWidget(self._forward_btn)

        self._up_btn = QPushButton("^")
        self._up_btn.setFixedWidth(30)
        self._up_btn.clicked.connect(self._go_up)
        toolbar.addWidget(self._up_btn)

        self._refresh_btn = QPushButton("R")
        self._refresh_btn.setFixedWidth(30)
        self._refresh_btn.clicked.connect(self._refresh)
        toolbar.addWidget(self._refresh_btn)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Ctrl+L / Cmd+L: Focus address bar
        focus_address_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        focus_address_shortcut.activated.connect(self._focus_address_bar)

        # F3: Search files
        search_shortcut = QShortcut(QKeySequence("F3"), self)
        search_shortcut.activated.connect(self._show_search_dialog)

        # F5: Refresh
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._refresh)

        # Backspace: Go up
        backspace_shortcut = QShortcut(QKeySequence("Backspace"), self)
        backspace_shortcut.activated.connect(self._go_up)

        # Alt+Left: Back
        back_shortcut = QShortcut(QKeySequence("Alt+Left"), self)
        back_shortcut.activated.connect(self._go_back)

        # Alt+Right: Forward
        forward_shortcut = QShortcut(QKeySequence("Alt+Right"), self)
        forward_shortcut.activated.connect(self._go_forward)

    def _focus_address_bar(self):
        """Focus and select address bar text."""
        self._address_bar.focus_and_select()

    def _show_search_dialog(self):
        """Show search dialog."""
        from commander.widgets.search_dialog import SearchDialog

        dialog = SearchDialog(self._current_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_selected_path()
            if result:
                if result.is_dir():
                    self._navigate_to(result)
                else:
                    self._navigate_to(result.parent)
                    # TODO: Select the file in list

    def _connect_signals(self):
        """Connect signals between components."""
        # Folder tree selection -> file list update
        self._folder_tree.folder_selected.connect(self._on_folder_selected)

        # Favorites panel selection
        self._favorites_panel.folder_selected.connect(self._navigate_to)

        # File list double click -> navigate or open
        self._file_list.item_activated.connect(self._on_item_activated)

        # File list selection -> preview update
        self._file_list.item_selected.connect(self._on_item_selected)

        # Address bar navigation
        self._address_bar.path_changed.connect(self._navigate_to)

        # Address bar favorite toggle -> refresh favorites panel
        self._address_bar.favorite_toggled.connect(self._on_favorite_toggled)

        # Undo manager signals
        undo_mgr = get_undo_manager()
        undo_mgr.undo_available.connect(self._on_undo_available)
        undo_mgr.redo_available.connect(self._on_redo_available)
        undo_mgr.action_performed.connect(self._on_undo_action_performed)

    def _on_favorite_toggled(self, path: Path, is_favorite: bool):
        """Handle favorite toggle."""
        self._favorites_panel.refresh()

    def _on_undo_available(self, available: bool):
        """Update undo action state."""
        self._undo_action.setEnabled(available)
        if available:
            desc = get_undo_manager().get_undo_description()
            self._undo_action.setText(f"Undo {desc}")
        else:
            self._undo_action.setText("Undo")

    def _on_redo_available(self, available: bool):
        """Update redo action state."""
        self._redo_action.setEnabled(available)
        if available:
            desc = get_undo_manager().get_redo_description()
            self._redo_action.setText(f"Redo {desc}")
        else:
            self._redo_action.setText("Redo")

    def _on_undo_action_performed(self, message: str):
        """Show undo/redo result in status bar."""
        self._status_bar.showMessage(message)
        self._refresh()

    def _load_settings(self):
        """Load saved settings."""
        # Window geometry
        geometry = self._settings.load_window_geometry()
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1200, 800)

        # Splitter sizes
        sizes = self._settings.load_splitter_sizes()
        if sizes:
            self._splitter.setSizes(sizes)

        # Last path - navigate to it (this also updates _current_path)
        last_path = self._settings.load_last_path()
        if last_path and last_path.exists():
            self._navigate_to(last_path)

        # View mode
        view_mode = self._settings.load_view_mode()
        self._file_list.set_view_mode(view_mode)

    def _save_settings(self):
        """Save current settings."""
        self._settings.save_window_geometry(self.saveGeometry())
        self._settings.save_splitter_sizes(self._splitter.sizes())
        self._settings.save_last_path(self._current_path)

    def closeEvent(self, event):
        """Save settings on close."""
        self._save_settings()
        super().closeEvent(event)

    def _navigate_to(self, path: Path):
        """Navigate to a directory."""
        if not path.exists() or not path.is_dir():
            return

        self._current_path = path
        self._address_bar.set_path(path)
        self._file_list.set_root_path(path)
        self._folder_tree.select_path(path)

        # Update history
        if self._history_index < len(self._history) - 1:
            self._history = self._history[: self._history_index + 1]
        if not self._history or self._history[-1] != path:
            self._history.append(path)
            self._history_index = len(self._history) - 1

        self._update_nav_buttons()
        self._update_status()

    def _on_folder_selected(self, path: Path):
        """Handle folder tree selection."""
        self._navigate_to(path)

    def _on_item_activated(self, path: Path):
        """Handle file list item double-click."""
        from commander.core.archive_handler import ArchiveManager

        if path.is_dir():
            self._navigate_to(path)
        elif ArchiveManager.is_archive(path):
            self._open_archive(path)
        elif self._is_image(path):
            self._open_image_viewer(path)

    def _on_item_selected(self, path: Path):
        """Handle file list item selection."""
        self._preview_panel.show_preview(path)

    def _is_image(self, path: Path) -> bool:
        """Check if path is an image file."""
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".ico", ".psd", ".psb"}
        return path.suffix.lower() in image_extensions

    def _open_image_viewer(self, path: Path):
        """Open fullscreen image viewer."""
        from commander.views.fullscreen_viewer import FullscreenImageViewer

        # Get list of images in current directory
        images = [
            p
            for p in self._current_path.iterdir()
            if p.is_file() and self._is_image(p)
        ]
        images.sort()

        self._viewer = FullscreenImageViewer(self)
        self._viewer.show_image(path, images)

    def _open_archive(self, path: Path):
        """Open archive browser."""
        from commander.views.archive_browser import ArchiveBrowser

        self._archive_browser = ArchiveBrowser(path, self)
        self._archive_browser.show()

    def _go_back(self):
        """Navigate back in history."""
        if self._history_index > 0:
            self._history_index -= 1
            path = self._history[self._history_index]
            self._current_path = path
            self._address_bar.set_path(path)
            self._file_list.set_root_path(path)
            self._folder_tree.select_path(path)
            self._update_nav_buttons()

    def _go_forward(self):
        """Navigate forward in history."""
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            path = self._history[self._history_index]
            self._current_path = path
            self._address_bar.set_path(path)
            self._file_list.set_root_path(path)
            self._folder_tree.select_path(path)
            self._update_nav_buttons()

    def _go_up(self):
        """Navigate to parent directory."""
        parent = self._current_path.parent
        if parent != self._current_path:
            self._navigate_to(parent)

    def _refresh(self):
        """Refresh current view."""
        self._file_list.set_root_path(self._current_path)

    def _update_nav_buttons(self):
        """Update navigation button states."""
        self._back_btn.setEnabled(self._history_index > 0)
        self._forward_btn.setEnabled(self._history_index < len(self._history) - 1)
        self._up_btn.setEnabled(self._current_path.parent != self._current_path)

    def _update_status(self):
        """Update status bar."""
        try:
            items = list(self._current_path.iterdir())
            dirs = sum(1 for p in items if p.is_dir())
            files = len(items) - dirs
            self._status_bar.showMessage(f"{dirs} folders, {files} files")
        except PermissionError:
            self._status_bar.showMessage("Access denied")

    def _copy_selected(self):
        """Copy selected items to clipboard."""
        paths = self._file_list.get_selected_paths()
        if paths:
            self._file_ops.copy_to_clipboard(paths)
            self._status_bar.showMessage(f"Copied {len(paths)} item(s)")

    def _cut_selected(self):
        """Cut selected items to clipboard."""
        paths = self._file_list.get_selected_paths()
        if paths:
            self._file_ops.cut_to_clipboard(paths)
            self._status_bar.showMessage(f"Cut {len(paths)} item(s)")

    def _paste(self):
        """Paste items from clipboard."""
        from commander.widgets.progress_dialog import ProgressDialog

        if not self._file_ops.has_clipboard():
            self._status_bar.showMessage("Nothing to paste")
            return

        # Use progress dialog for paste operation
        dialog = ProgressDialog("paste", [], self._current_path, self)
        result = dialog.exec()

        if result:
            count = dialog.get_result()
            self._refresh()
            if count > 0:
                self._status_bar.showMessage(f"Pasted {count} item(s)")
            else:
                self._status_bar.showMessage("Paste cancelled")

    def _delete_selected(self):
        """Delete selected items."""
        paths = self._file_list.get_selected_paths()
        if paths:
            count = self._file_ops.delete(paths)
            self._refresh()
            self._status_bar.showMessage(f"Deleted {count} item(s)")

    def _rename_selected(self):
        """Rename selected item."""
        self._file_list.start_rename()

    def _undo(self):
        """Undo last file operation."""
        get_undo_manager().undo()

    def _redo(self):
        """Redo last undone operation."""
        get_undo_manager().redo()

    def _create_new_folder(self):
        """Create a new folder."""
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            result = self._file_ops.create_folder(self._current_path, name)
            if result:
                self._refresh()
                self._status_bar.showMessage(f"Created folder: {name}")
            else:
                self._status_bar.showMessage(f"Error creating folder: {name}")
