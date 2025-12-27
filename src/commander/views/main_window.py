"""Main window with 3-panel layout."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QFileSystemWatcher
from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QWidget,
    QVBoxLayout,
    QToolBar,
    QPushButton,
    QStatusBar,
    QInputDialog,
    QDialog,
)
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from commander.views.folder_tree import FolderTreeView
from commander.views.file_list import FileListView
from commander.views.preview_panel import PreviewPanel
from commander.widgets.address_bar import AddressBar
from commander.widgets.favorites_panel import FavoritesPanel
from commander.core.file_operations import FileOperations
from commander.core.undo_manager import get_undo_manager
from commander.utils.settings import Settings
from commander.utils.i18n import tr
from commander.utils.update_checker import check_for_updates_async, ReleaseInfo
from commander.utils.logger import get_logger

_logger = get_logger()


class MainWindow(QMainWindow):
    """Main window with explorer-style 3-panel layout."""

    def __init__(self):
        _logger.info("MainWindow.__init__ started")
        super().__init__()
        self._settings = Settings()
        self._current_path: Path = Path.home()
        self._history: list[Path] = [self._current_path]
        self._history_index: int = 0
        self._file_ops = FileOperations()

        # File system watcher for external changes
        self._watcher = QFileSystemWatcher()
        self._watcher.directoryChanged.connect(self._on_directory_changed)

        _logger.debug("Setting up toolbar...")
        self._setup_toolbar()
        _logger.debug("Setting up UI...")
        self._setup_ui()
        _logger.debug("Setting up menu...")
        self._setup_menu()
        _logger.debug("Setting up shortcuts...")
        self._setup_shortcuts()
        _logger.debug("Connecting signals...")
        self._connect_signals()
        _logger.debug("Loading settings...")
        self._load_settings()
        _logger.debug("Checking for updates...")
        self._check_for_updates()

        _logger.debug("Updating window title...")
        self._update_window_title()
        _logger.debug("Window title updated")

        # Keep reference to update thread
        self._update_thread = None
        _logger.info("MainWindow.__init__ completed, about to return")

    def _setup_ui(self):
        """Setup the main UI layout."""
        _logger.debug("_setup_ui: Creating central widget...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Address bar
        _logger.debug("_setup_ui: Creating AddressBar...")
        self._address_bar = AddressBar()
        main_layout.addWidget(self._address_bar)

        # 3-panel splitter
        _logger.debug("_setup_ui: Creating splitter...")
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Favorites + Folder tree
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        _logger.debug("_setup_ui: Creating FavoritesPanel...")
        self._favorites_panel = FavoritesPanel()
        _logger.debug("_setup_ui: Creating FolderTreeView...")
        self._folder_tree = FolderTreeView()

        left_layout.addWidget(self._favorites_panel)
        left_layout.addWidget(self._folder_tree, stretch=1)

        _logger.debug("_setup_ui: Creating FileListView...")
        self._file_list = FileListView()
        _logger.debug("_setup_ui: Creating PreviewPanel...")
        self._preview_panel = PreviewPanel()

        self._splitter.addWidget(left_panel)
        self._splitter.addWidget(self._file_list)
        self._splitter.addWidget(self._preview_panel)

        # Default sizes (1:3:1 ratio)
        self._splitter.setSizes([200, 600, 200])

        main_layout.addWidget(self._splitter, stretch=1)

        # Status bar
        _logger.debug("_setup_ui: Creating status bar...")
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        # Navigate to home
        _logger.debug(f"_setup_ui: Navigating to {self._current_path}...")
        self._navigate_to(self._current_path)
        _logger.debug("_setup_ui completed")

    def _setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu(tr("menu_file"))

        new_window_action = QAction(tr("new_window"), self)
        new_window_action.setShortcut(QKeySequence("Ctrl+N"))
        new_window_action.triggered.connect(self._open_new_window)
        file_menu.addAction(new_window_action)

        file_menu.addSeparator()

        new_folder_action = QAction(tr("new_folder"), self)
        new_folder_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        new_folder_action.triggered.connect(self._create_new_folder)
        file_menu.addAction(new_folder_action)

        file_menu.addSeparator()

        exit_action = QAction(tr("exit"), self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu(tr("menu_edit"))

        # Undo/Redo
        self._undo_action = QAction(tr("undo"), self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self._undo)
        self._undo_action.setEnabled(False)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction(tr("redo"), self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.triggered.connect(self._redo)
        self._redo_action.setEnabled(False)
        edit_menu.addAction(self._redo_action)

        edit_menu.addSeparator()

        self._copy_action = QAction(tr("copy"), self)
        self._copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self._copy_action.triggered.connect(self._copy_selected)
        edit_menu.addAction(self._copy_action)

        self._cut_action = QAction(tr("cut"), self)
        self._cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        self._cut_action.triggered.connect(self._cut_selected)
        edit_menu.addAction(self._cut_action)

        self._paste_action = QAction(tr("paste"), self)
        self._paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self._paste_action.triggered.connect(self._paste)
        edit_menu.addAction(self._paste_action)

        edit_menu.addSeparator()

        self._delete_action = QAction(tr("delete"), self)
        self._delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self._delete_action.triggered.connect(self._delete_selected)
        edit_menu.addAction(self._delete_action)

        self._rename_action = QAction(tr("rename"), self)
        self._rename_action.setShortcut(QKeySequence("F2"))
        self._rename_action.triggered.connect(self._rename_selected)
        edit_menu.addAction(self._rename_action)

        # View menu
        view_menu = menubar.addMenu(tr("menu_view"))

        self._list_view_action = QAction(tr("view_list"), self)
        self._list_view_action.triggered.connect(lambda: self._file_list.set_view_mode("list"))
        view_menu.addAction(self._list_view_action)

        self._icon_view_action = QAction(tr("view_icons"), self)
        self._icon_view_action.triggered.connect(lambda: self._file_list.set_view_mode("icons"))
        view_menu.addAction(self._icon_view_action)

        self._thumb_view_action = QAction(tr("view_thumbnails"), self)
        self._thumb_view_action.triggered.connect(
            lambda: self._file_list.set_view_mode("thumbnails")
        )
        view_menu.addAction(self._thumb_view_action)

        # Settings action (goes to app menu on macOS automatically)
        settings_action = QAction(tr("settings") + "...", self)
        settings_action.setShortcut(QKeySequence.StandardKey.Preferences)
        settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        settings_action.triggered.connect(self._show_settings)
        # Add to Edit menu for cross-platform consistency
        edit_menu.addSeparator()
        edit_menu.addAction(settings_action)

        # Custom commands action
        custom_commands_action = QAction(tr("custom_commands"), self)
        custom_commands_action.triggered.connect(self._show_custom_commands)
        edit_menu.addAction(custom_commands_action)

        # Help menu
        help_menu = menubar.addMenu(tr("menu_help"))

        shortcuts_action = QAction(tr("shortcuts") + "...", self)
        shortcuts_action.setShortcut(QKeySequence("F1"))
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        check_updates_action = QAction(tr("check_for_updates") + "...", self)
        check_updates_action.triggered.connect(self._manual_check_for_updates)
        help_menu.addAction(check_updates_action)

        help_menu.addSeparator()

        about_action = QAction(tr("about"), self)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_settings(self):
        """Show settings dialog."""
        from commander.widgets.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self)
        dialog.exec()

    def _show_custom_commands(self):
        """Show custom commands dialog."""
        from commander.widgets.custom_commands_dialog import CustomCommandsDialog

        dialog = CustomCommandsDialog(self)
        dialog.exec()

    def _show_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        from commander.widgets.shortcuts_dialog import ShortcutsDialog

        dialog = ShortcutsDialog(self)
        dialog.exec()

    def _show_about(self):
        """Show about dialog."""
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.about(
            self,
            tr("about"),
            f"<h2>{tr('app_name')}</h2>"
            f"<p>{tr('about_description')}</p>"
            f"<p>{tr('about_version')}: 1.0.0</p>",
        )

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

        # Back: Cmd+Left (macOS) / Alt+Left (others)
        if sys.platform == "darwin":
            back_shortcut = QShortcut(QKeySequence("Ctrl+Left"), self)  # Cmd = Ctrl in Qt
        else:
            back_shortcut = QShortcut(QKeySequence("Alt+Left"), self)
        back_shortcut.activated.connect(self._go_back)

        # Forward: Cmd+Right (macOS) / Alt+Right (others)
        if sys.platform == "darwin":
            forward_shortcut = QShortcut(QKeySequence("Ctrl+Right"), self)
        else:
            forward_shortcut = QShortcut(QKeySequence("Alt+Right"), self)
        forward_shortcut.activated.connect(self._go_forward)

        # Cmd+Up (macOS) / Ctrl+Up: Go to parent folder
        # Note: On macOS, Qt maps Cmd key to Ctrl (not Meta)
        up_shortcut = QShortcut(QKeySequence("Ctrl+Up"), self)
        down_shortcut = QShortcut(QKeySequence("Ctrl+Down"), self)
        up_shortcut.activated.connect(self._go_up)

        # Cmd+Down (macOS) / Ctrl+Down: Open selected item
        down_shortcut.activated.connect(self._open_selected)

    def _open_selected(self):
        """Open selected item (folder or file)."""
        paths = self._file_list.get_selected_paths()
        if paths:
            self._on_item_activated(paths[0])

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

        # Folder tree drag and drop
        self._folder_tree.files_dropped.connect(self._on_files_dropped)

        # Folder tree request new window
        self._folder_tree.request_new_window.connect(self._open_new_window_at)

        # Favorites panel selection
        self._favorites_panel.folder_selected.connect(self._navigate_to)

        # File list double click -> navigate or open
        self._file_list.item_activated.connect(self._on_item_activated)

        # File list selection -> preview update
        self._file_list.item_selected.connect(self._on_item_selected)

        # File list request new window
        self._file_list.request_new_window.connect(self._open_new_window_at)

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
        _logger.debug("_load_settings started")
        # Window geometry
        geometry = self._settings.load_window_geometry()
        if geometry:
            self.restoreGeometry(geometry)
            _logger.debug("Window geometry restored")
        else:
            self.resize(1200, 800)
            _logger.debug("Using default window size 1200x800")

        # Splitter sizes
        sizes = self._settings.load_splitter_sizes()
        if sizes:
            self._splitter.setSizes(sizes)
            _logger.debug(f"Splitter sizes restored: {sizes}")

        # Last path - navigate to it (this also updates _current_path)
        last_path = self._settings.load_last_path()
        _logger.debug(f"Last path from settings: {last_path}")
        if last_path and last_path.exists():
            self._navigate_to(last_path)

        # View mode
        view_mode = self._settings.load_view_mode()
        self._file_list.set_view_mode(view_mode)
        _logger.debug(f"View mode set to: {view_mode}")
        _logger.debug("_load_settings completed")

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
        _logger.debug(f"_navigate_to: {path}")
        if not path.exists() or not path.is_dir():
            _logger.warning(f"Path does not exist or is not a directory: {path}")
            return

        # Update file system watcher
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        self._watcher.addPath(str(path))

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
        _logger.debug(f"Navigation to {path} completed")

    def _on_folder_selected(self, path: Path):
        """Handle folder tree selection."""
        self._navigate_to(path)

    def _on_item_activated(self, path: Path):
        """Handle file list item double-click."""
        import subprocess
        from commander.core.archive_handler import ArchiveManager

        # Check for macOS app bundle (.app is a directory but should be launched)
        is_app_bundle = sys.platform == "darwin" and path.suffix.lower() == ".app"

        if path.is_dir() and not is_app_bundle:
            self._navigate_to(path)
        elif ArchiveManager.is_archive(path):
            self._open_archive(path)
        elif self._is_image(path):
            self._open_image_viewer(path)
        else:
            # Open with system default app
            if sys.platform == "darwin":
                subprocess.run(["open", str(path)])
            elif sys.platform == "win32":
                import os

                os.startfile(str(path))
            else:
                subprocess.run(["xdg-open", str(path)])

    def _on_item_selected(self, path: Path):
        """Handle file list item selection."""
        self._preview_panel.show_preview(path)

    def _is_image(self, path: Path) -> bool:
        """Check if path is an image file."""
        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".tiff",
            ".ico",
            ".psd",
            ".psb",
        }
        return path.suffix.lower() in image_extensions

    def _open_image_viewer(self, path: Path):
        """Open fullscreen image viewer."""
        from commander.views.viewer import FullscreenImageViewer

        # Get list of images in current directory
        images = [p for p in self._current_path.iterdir() if p.is_file() and self._is_image(p)]
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
        self._update_status()

    def _on_directory_changed(self, path: str):
        """Handle external directory changes."""
        # Check if it's the current directory
        if Path(path) == self._current_path:
            self._refresh()

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

    def _get_focused_paths(self) -> list[Path]:
        """Get selected paths from the focused panel."""
        # Check if folder tree has focus
        if self._folder_tree.hasFocus():
            path = self._folder_tree.get_selected_path()
            return [path] if path else []
        # Default to file list
        return self._file_list.get_selected_paths()

    def _copy_selected(self):
        """Copy selected items to clipboard."""
        paths = self._get_focused_paths()
        if paths:
            self._file_ops.copy_to_clipboard(paths)
            self._status_bar.showMessage(f"Copied {len(paths)} item(s)")

    def _cut_selected(self):
        """Cut selected items to clipboard."""
        paths = self._get_focused_paths()
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

        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            result = self._file_ops.create_folder(self._current_path, name)
            if result:
                self._refresh()
                self._status_bar.showMessage(f"Created folder: {name}")
            else:
                self._status_bar.showMessage(f"Error creating folder: {name}")

    def _check_for_updates(self):
        """Check for updates in background (silent)."""
        try:
            self._update_thread = check_for_updates_async(self._on_update_check_complete)
            _logger.debug("Update check thread started")
        except Exception as e:
            _logger.error(f"Failed to start update check: {e}", exc_info=True)

    def _manual_check_for_updates(self):
        """Manually check for updates (shows result even if up to date)."""
        self._update_thread = check_for_updates_async(self._on_manual_update_check_complete)

    def _on_update_check_complete(self, release_info: "ReleaseInfo | None"):
        """Handle automatic update check result (silent if no update)."""
        if release_info:
            self._show_update_notification(release_info)

    def _on_manual_update_check_complete(self, release_info: "ReleaseInfo | None"):
        """Handle manual update check result (always shows message)."""
        if release_info:
            self._show_update_notification(release_info)
        else:
            from PySide6.QtWidgets import QMessageBox

            msg = QMessageBox(self)
            msg.setWindowTitle(tr("check_for_updates"))
            msg.setText(tr("no_updates_available"))
            msg.setIconPixmap(self.windowIcon().pixmap(64, 64))
            msg.exec()

    def _show_update_notification(self, release_info: "ReleaseInfo"):
        """Show update available notification."""
        from PySide6.QtWidgets import QMessageBox
        import webbrowser

        msg = QMessageBox(self)
        msg.setIconPixmap(self.windowIcon().pixmap(64, 64))
        msg.setWindowTitle(tr("update_available"))
        msg.setText(f"{tr('new_version_available')}: v{release_info.version}")
        msg.setInformativeText(tr("update_download_prompt"))

        download_btn = msg.addButton(tr("download"), QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(tr("later"), QMessageBox.ButtonRole.RejectRole)

        msg.exec()

        if msg.clickedButton() == download_btn:
            webbrowser.open(release_info.html_url)

    def _update_window_title(self):
        """Update window title with version info."""
        from commander import __version__, get_build_date

        title = tr("app_name")
        if __version__:
            title += f" v{__version__}"
        build_date = get_build_date()
        if build_date:
            title += f" ({build_date})"
        self.setWindowTitle(title)

    def _open_new_window(self):
        """Open a new window at current path."""
        self._open_new_window_at(self._current_path)

    def _open_new_window_at(self, path: Path):
        """Open a new window at specified path."""
        from commander.__main__ import get_window_manager

        window = get_window_manager().create_window(path)
        window.show()

    def _on_files_dropped(self, paths: list[Path], destination: Path):
        """Handle files dropped onto folder tree."""
        from PySide6.QtWidgets import QMessageBox
        from commander.widgets.progress_dialog import ProgressDialog

        # Filter out files already in destination
        paths_to_copy = [p for p in paths if p.parent != destination]
        if not paths_to_copy:
            return

        # Ask user: Copy or Move?
        reply = QMessageBox.question(
            self,
            tr("drop_files"),
            tr("drop_copy_or_move").format(count=len(paths_to_copy)),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Cancel:
            return

        if reply == QMessageBox.StandardButton.Yes:
            dialog = ProgressDialog("copy", paths_to_copy, destination, self)
            dialog.exec()
        else:
            dialog = ProgressDialog("move", paths_to_copy, destination, self)
            dialog.exec()

        self._refresh()
