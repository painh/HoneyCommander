"""Main window with tab support and 3-panel layout."""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QPushButton,
    QStatusBar,
    QInputDialog,
    QDialog,
    QStackedWidget,
)
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from commander.widgets.tab_bar import CommanderTabBar
from commander.widgets.tab_content import TabContentWidget
from commander.core.tab_manager import TabManager
from commander.core.file_operations import FileOperations
from commander.core.undo_manager import get_undo_manager
from commander.utils.settings import Settings
from commander.utils.i18n import tr
from commander.utils.update_checker import check_for_updates_async, ReleaseInfo
from commander.utils.logger import get_logger

_logger = get_logger()


class MainWindow(QMainWindow):
    """Main window with tab support and explorer-style 3-panel layout."""

    def __init__(self, initial_path: Path = None, tab_data: dict = None):
        """Initialize main window.

        Args:
            initial_path: Initial path for the first tab.
            tab_data: Optional serialized tab data to restore.
        """
        _logger.info("MainWindow.__init__ started")
        super().__init__()
        self._settings = Settings()
        self._file_ops = FileOperations()
        self._initial_path = initial_path
        self._initial_tab_data = tab_data

        _logger.debug("Setting up toolbar...")
        self._setup_toolbar()
        _logger.debug("Setting up UI...")
        self._setup_ui()
        _logger.debug("Setting up menu...")
        self._setup_menu()
        _logger.debug("Setting up shortcuts...")
        self._setup_shortcuts()
        _logger.debug("Loading settings...")
        self._load_settings()
        _logger.debug("Checking for updates...")
        self._check_for_updates()

        _logger.debug("Updating window title...")
        self._update_window_title()
        _logger.debug("Window title updated")

        # Keep reference to update thread
        self._update_thread = None
        _logger.info("MainWindow.__init__ completed")

    def _setup_ui(self):
        """Setup the main UI layout with tabs."""
        _logger.debug("_setup_ui: Creating central widget...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Tab bar container (tab bar + new tab button)
        tab_bar_container = QWidget()
        tab_bar_container.setStyleSheet("""
            QWidget {
                background-color: #252526;
                border-bottom: 1px solid #3c3c3c;
            }
        """)
        tab_bar_layout = QHBoxLayout(tab_bar_container)
        tab_bar_layout.setContentsMargins(4, 4, 4, 0)
        tab_bar_layout.setSpacing(4)

        # Tab bar
        _logger.debug("_setup_ui: Creating tab bar...")
        self._tab_bar = CommanderTabBar()
        tab_bar_layout.addWidget(self._tab_bar, stretch=1)

        # New tab button
        self._new_tab_btn = QPushButton("+")
        self._new_tab_btn.setFixedSize(32, 32)
        self._new_tab_btn.setToolTip("New Tab (Ctrl+T)")
        self._new_tab_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #454545;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
        """)
        self._new_tab_btn.clicked.connect(self._create_new_tab)
        tab_bar_layout.addWidget(self._new_tab_btn)

        main_layout.addWidget(tab_bar_container)

        # Tab content stack
        _logger.debug("_setup_ui: Creating tab stack...")
        self._tab_stack = QStackedWidget()
        main_layout.addWidget(self._tab_stack, stretch=1)

        # Tab manager
        _logger.debug("_setup_ui: Creating tab manager...")
        self._tab_manager = TabManager(self._tab_stack, self)
        self._connect_tab_signals()

        # Status bar
        _logger.debug("_setup_ui: Creating status bar...")
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

        # Create initial tab
        _logger.debug("_setup_ui: Creating initial tab...")
        if self._initial_tab_data:
            self._tab_manager.merge_tab(self._initial_tab_data)
        else:
            path = self._initial_path or Path.home()
            self._tab_manager.create_tab(path)

        _logger.debug("_setup_ui completed")

    def _connect_tab_signals(self):
        """Connect tab-related signals."""
        # Tab bar signals
        self._tab_bar.currentChanged.connect(self._on_tab_bar_changed)
        self._tab_bar.close_tab_requested.connect(self._close_tab)
        self._tab_bar.new_tab_requested.connect(self._create_new_tab)
        self._tab_bar.tab_detach_requested.connect(self._detach_tab)
        self._tab_bar.tab_drop_received.connect(self._on_tab_drop_received)
        self._tab_bar.duplicate_tab_requested.connect(self._duplicate_tab)
        self._tab_bar.close_other_tabs_requested.connect(self._close_other_tabs)
        self._tab_bar.close_tabs_to_right_requested.connect(self._close_tabs_to_right)

        # Tab manager signals
        self._tab_manager.tab_added.connect(self._on_tab_added)
        self._tab_manager.tab_removed.connect(self._on_tab_removed)
        self._tab_manager.current_tab_changed.connect(self._on_current_tab_changed)
        self._tab_manager.tab_title_changed.connect(self._on_tab_title_changed)
        self._tab_manager.all_tabs_closed.connect(self.close)

        # Undo manager signals
        undo_mgr = get_undo_manager()
        undo_mgr.undo_available.connect(self._on_undo_available)
        undo_mgr.redo_available.connect(self._on_redo_available)
        undo_mgr.action_performed.connect(self._on_undo_action_performed)

    def _connect_tab_content_signals(self, tab: TabContentWidget):
        """Connect signals for a specific tab content."""
        tab.item_activated.connect(self._on_item_activated)
        tab.files_dropped.connect(self._on_files_dropped)
        tab.request_new_window.connect(self._open_new_window_at)

    # === Tab Bar Event Handlers ===

    def _on_tab_bar_changed(self, index: int):
        """Handle tab bar selection change."""
        if index >= 0:
            self._tab_manager.switch_to_tab(index)

    def _on_tab_added(self, index: int):
        """Handle new tab added."""
        from PySide6.QtWidgets import QFileIconProvider

        tab = self._tab_manager.get_tab(index)
        if tab:
            self._connect_tab_content_signals(tab)

            # Add to tab bar with folder icon
            icon_provider = QFileIconProvider()
            folder_icon = icon_provider.icon(QFileIconProvider.IconType.Folder)

            self._tab_bar.insertTab(index, folder_icon, tab.get_tab_title())
            self._tab_bar.setTabToolTip(index, tab.get_tab_tooltip())

    def _on_tab_removed(self, index: int):
        """Handle tab removed."""
        self._tab_bar.removeTab(index)

    def _on_current_tab_changed(self, index: int, tab: TabContentWidget):
        """Handle current tab change."""
        # Sync tab bar
        if self._tab_bar.currentIndex() != index:
            self._tab_bar.setCurrentIndex(index)

        # Update nav buttons
        self._update_nav_buttons()
        self._update_status()
        self._update_window_title()

    def _on_tab_title_changed(self, index: int, title: str):
        """Handle tab title change."""
        tab = self._tab_manager.get_tab(index)
        if tab:
            self._tab_bar.update_tab(index, title, tab.get_tab_tooltip())

        # Update window title if current tab
        if index == self._tab_manager.current_index:
            self._update_window_title()

    def _on_tab_drop_received(self, tab_info: dict, insert_index: int):
        """Handle tab dropped from another window."""
        from commander.__main__ import get_window_manager

        source_window_id = tab_info.get("source_window_id")
        source_tab_index = tab_info.get("tab_index")

        # Find source window
        for window in get_window_manager().get_windows():
            if id(window) == source_window_id:
                # Get tab data from source
                tab_data = window._tab_manager.detach_tab(source_tab_index)
                if tab_data:
                    self._tab_manager.merge_tab(tab_data, insert_index)
                break

    # === Tab Operations ===

    def _create_new_tab(self):
        """Create new tab at current path."""
        current_tab = self._tab_manager.get_current_tab()
        path = current_tab.current_path if current_tab else Path.home()
        self._tab_manager.create_tab(path)

    def _close_tab(self, index: int = None):
        """Close tab at index (or current tab)."""
        if index is None:
            index = self._tab_manager.current_index
        self._tab_manager.close_tab(index)

    def _close_other_tabs(self, keep_index: int):
        """Close all tabs except one."""
        self._tab_manager.close_other_tabs(keep_index)

    def _close_tabs_to_right(self, index: int):
        """Close tabs to the right."""
        self._tab_manager.close_tabs_to_right(index)

    def _duplicate_tab(self, index: int):
        """Duplicate tab."""
        self._tab_manager.duplicate_tab(index)

    def _detach_tab(self, index: int, global_pos):
        """Detach tab to new window."""
        from commander.__main__ import get_window_manager

        tab_data = self._tab_manager.detach_tab(index)
        if tab_data:
            window = get_window_manager().create_window_from_tab(tab_data)
            window.move(global_pos.x() - 100, global_pos.y() - 50)
            window.show()

    def _next_tab(self):
        """Switch to next tab."""
        self._tab_manager.next_tab()

    def _prev_tab(self):
        """Switch to previous tab."""
        self._tab_manager.prev_tab()

    def _switch_to_tab_number(self, number: int):
        """Switch to tab by number (1-9)."""
        self._tab_manager.switch_to_tab_number(number)

    def _reopen_closed_tab(self):
        """Reopen most recently closed tab."""
        if self._tab_manager.has_closed_tabs():
            self._tab_manager.reopen_closed_tab()
        else:
            self._status_bar.showMessage("No recently closed tabs")

    # === Navigation (delegated to current tab) ===

    def _go_back(self):
        """Navigate back in current tab."""
        tab = self._tab_manager.get_current_tab()
        if tab:
            tab.go_back()
            self._update_nav_buttons()

    def _go_forward(self):
        """Navigate forward in current tab."""
        tab = self._tab_manager.get_current_tab()
        if tab:
            tab.go_forward()
            self._update_nav_buttons()

    def _go_up(self):
        """Navigate up in current tab."""
        tab = self._tab_manager.get_current_tab()
        if tab:
            tab.go_up()
            self._update_nav_buttons()

    def _refresh(self):
        """Refresh current tab."""
        tab = self._tab_manager.get_current_tab()
        if tab:
            tab.refresh()
            self._update_status()

    def _update_nav_buttons(self):
        """Update navigation button states."""
        tab = self._tab_manager.get_current_tab()
        if tab:
            self._back_btn.setEnabled(tab.can_go_back)
            self._forward_btn.setEnabled(tab.can_go_forward)
            self._up_btn.setEnabled(tab.can_go_up)
        else:
            self._back_btn.setEnabled(False)
            self._forward_btn.setEnabled(False)
            self._up_btn.setEnabled(False)

    # === File Operations ===

    def _on_item_activated(self, path: Path):
        """Handle file activation (non-directory)."""
        import subprocess
        from commander.core.archive_handler import ArchiveManager

        # Check for macOS app bundle
        is_app_bundle = sys.platform == "darwin" and path.suffix.lower() == ".app"

        if path.is_dir() and not is_app_bundle:
            # This shouldn't happen as TabContentWidget handles directories
            tab = self._tab_manager.get_current_tab()
            if tab:
                tab.navigate_to(path)
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

        tab = self._tab_manager.get_current_tab()
        if not tab:
            return

        current_path = tab.current_path
        images = [p for p in current_path.iterdir() if p.is_file() and self._is_image(p)]
        images.sort()

        self._viewer = FullscreenImageViewer(self)
        self._viewer.show_image(path, images)

    def _open_archive(self, path: Path):
        """Open archive browser."""
        from commander.views.archive_browser import ArchiveBrowser
        from commander.core.archive_handler import ArchiveManager
        from PySide6.QtWidgets import QMessageBox

        tab = self._tab_manager.get_current_tab()

        threshold_mb = self._settings.load_archive_size_threshold()
        if threshold_mb > 0:
            try:
                file_size_mb = path.stat().st_size / (1024 * 1024)
                if file_size_mb >= threshold_mb:
                    if file_size_mb >= 1024:
                        size_str = f"{file_size_mb / 1024:.1f} GB"
                    else:
                        size_str = f"{file_size_mb:.1f} MB"

                    msg = QMessageBox(self)
                    msg.setWindowTitle(tr("archive_large_title"))
                    msg.setText(tr("archive_large_message").replace("{size}", size_str))
                    msg.setIcon(QMessageBox.Question)

                    extract_btn = msg.addButton(tr("archive_extract"), QMessageBox.AcceptRole)
                    browse_btn = msg.addButton(tr("archive_browse"), QMessageBox.RejectRole)
                    msg.addButton(tr("cancel"), QMessageBox.RejectRole)

                    msg.exec()

                    if msg.clickedButton() == extract_btn:
                        extract_dir = ArchiveManager.smart_extract(path, path.parent)
                        if tab:
                            tab.navigate_to(extract_dir)
                        return
                    elif msg.clickedButton() == browse_btn:
                        pass
                    else:
                        return
            except OSError:
                pass

        self._archive_browser = ArchiveBrowser(path, self)
        self._archive_browser.show()

    def _on_files_dropped(self, paths: list[Path], destination: Path):
        """Handle files dropped onto folder tree."""
        from PySide6.QtWidgets import QMessageBox
        from commander.widgets.progress_dialog import ProgressDialog

        paths_to_copy = [p for p in paths if p.parent != destination]
        if not paths_to_copy:
            return

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

    def _get_focused_paths(self) -> list[Path]:
        """Get selected paths from the focused panel."""
        tab = self._tab_manager.get_current_tab()
        if not tab:
            return []

        if tab.folder_tree.hasFocus():
            path = tab.folder_tree.get_selected_path()
            return [path] if path else []
        return tab.get_selected_paths()

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

        tab = self._tab_manager.get_current_tab()
        if not tab:
            return

        if not self._file_ops.has_clipboard():
            self._status_bar.showMessage("Nothing to paste")
            return

        dialog = ProgressDialog("paste", [], tab.current_path, self)
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
        tab = self._tab_manager.get_current_tab()
        if not tab:
            return

        paths = tab.get_selected_paths()
        if paths:
            count = self._file_ops.delete(paths)
            self._refresh()
            self._status_bar.showMessage(f"Deleted {count} item(s)")

    def _rename_selected(self):
        """Rename selected item."""
        tab = self._tab_manager.get_current_tab()
        if tab:
            tab.file_list.start_rename()

    def _undo(self):
        """Undo last file operation."""
        get_undo_manager().undo()

    def _redo(self):
        """Redo last undone operation."""
        get_undo_manager().redo()

    def _create_new_folder(self):
        """Create a new folder."""
        tab = self._tab_manager.get_current_tab()
        if not tab:
            return

        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            result = self._file_ops.create_folder(tab.current_path, name)
            if result:
                self._refresh()
                self._status_bar.showMessage(f"Created folder: {name}")
            else:
                self._status_bar.showMessage(f"Error creating folder: {name}")

    # === Menu and Toolbar ===

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

    def _setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu(tr("menu_file"))

        new_tab_action = QAction(tr("new_tab") if tr("new_tab") != "new_tab" else "New Tab", self)
        new_tab_action.setShortcut(QKeySequence("Ctrl+T"))
        new_tab_action.triggered.connect(self._create_new_tab)
        file_menu.addAction(new_tab_action)

        close_tab_action = QAction(
            tr("close_tab") if tr("close_tab") != "close_tab" else "Close Tab", self
        )
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_action.triggered.connect(lambda: self._close_tab())
        file_menu.addAction(close_tab_action)

        reopen_tab_action = QAction(
            tr("reopen_tab") if tr("reopen_tab") != "reopen_tab" else "Reopen Closed Tab", self
        )
        reopen_tab_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        reopen_tab_action.triggered.connect(self._reopen_closed_tab)
        file_menu.addAction(reopen_tab_action)

        file_menu.addSeparator()

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
        self._list_view_action.triggered.connect(lambda: self._set_view_mode("list"))
        view_menu.addAction(self._list_view_action)

        self._icon_view_action = QAction(tr("view_icons"), self)
        self._icon_view_action.triggered.connect(lambda: self._set_view_mode("icons"))
        view_menu.addAction(self._icon_view_action)

        self._thumb_view_action = QAction(tr("view_thumbnails"), self)
        self._thumb_view_action.triggered.connect(lambda: self._set_view_mode("thumbnails"))
        view_menu.addAction(self._thumb_view_action)

        # Settings action
        settings_action = QAction(tr("settings") + "...", self)
        settings_action.setShortcut(QKeySequence.StandardKey.Preferences)
        settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        settings_action.triggered.connect(self._show_settings)
        edit_menu.addSeparator()
        edit_menu.addAction(settings_action)

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

    def _set_view_mode(self, mode: str):
        """Set view mode for current tab."""
        tab = self._tab_manager.get_current_tab()
        if tab:
            tab.set_view_mode(mode)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Focus address bar
        focus_address_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        focus_address_shortcut.activated.connect(self._focus_address_bar)

        # Search
        search_shortcut = QShortcut(QKeySequence("F3"), self)
        search_shortcut.activated.connect(self._show_search_dialog)

        # Refresh
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._refresh)

        # Go up
        backspace_shortcut = QShortcut(QKeySequence("Backspace"), self)
        backspace_shortcut.activated.connect(self._go_up)

        # Back/Forward
        if sys.platform == "darwin":
            back_shortcut = QShortcut(QKeySequence("Ctrl+Left"), self)
            forward_shortcut = QShortcut(QKeySequence("Ctrl+Right"), self)
        else:
            back_shortcut = QShortcut(QKeySequence("Alt+Left"), self)
            forward_shortcut = QShortcut(QKeySequence("Alt+Right"), self)
        back_shortcut.activated.connect(self._go_back)
        forward_shortcut.activated.connect(self._go_forward)

        # Up/Down navigation
        up_shortcut = QShortcut(QKeySequence("Ctrl+Up"), self)
        down_shortcut = QShortcut(QKeySequence("Ctrl+Down"), self)
        up_shortcut.activated.connect(self._go_up)
        down_shortcut.activated.connect(self._open_selected)

        # Tab navigation
        next_tab_shortcut = QShortcut(QKeySequence("Ctrl+Tab"), self)
        next_tab_shortcut.activated.connect(self._next_tab)

        prev_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        prev_tab_shortcut.activated.connect(self._prev_tab)

        # Tab number shortcuts (Ctrl+1 through Ctrl+9)
        for i in range(1, 10):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            shortcut.activated.connect(lambda n=i: self._switch_to_tab_number(n))

    def _focus_address_bar(self):
        """Focus and select address bar text."""
        tab = self._tab_manager.get_current_tab()
        if tab:
            tab.address_bar.focus_and_select()

    def _open_selected(self):
        """Open selected item."""
        tab = self._tab_manager.get_current_tab()
        if tab:
            paths = tab.get_selected_paths()
            if paths:
                self._on_item_activated(paths[0])

    def _show_search_dialog(self):
        """Show search dialog."""
        from commander.widgets.search_dialog import SearchDialog

        tab = self._tab_manager.get_current_tab()
        if not tab:
            return

        dialog = SearchDialog(tab.current_path, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_selected_path()
            if result:
                if result.is_dir():
                    tab.navigate_to(result)
                else:
                    tab.navigate_to(result.parent)

    # === Dialogs ===

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

    # === Undo/Redo ===

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

    # === Window Operations ===

    def _open_new_window(self):
        """Open a new window at current path."""
        tab = self._tab_manager.get_current_tab()
        path = tab.current_path if tab else Path.home()
        self._open_new_window_at(path)

    def _open_new_window_at(self, path: Path):
        """Open a new window at specified path."""
        from commander.__main__ import get_window_manager

        window = get_window_manager().create_window(path)
        window.show()

    # === Status and Title ===

    def _update_status(self):
        """Update status bar."""
        tab = self._tab_manager.get_current_tab()
        if not tab:
            self._status_bar.showMessage("No tabs open")
            return

        try:
            items = list(tab.current_path.iterdir())
            dirs = sum(1 for p in items if p.is_dir())
            files = len(items) - dirs
            self._status_bar.showMessage(f"{dirs} folders, {files} files")
        except PermissionError:
            self._status_bar.showMessage("Access denied")

    def _update_window_title(self):
        """Update window title with version and current tab info."""
        from commander import __version__, get_build_date

        title = tr("app_name")
        if __version__:
            title += f" v{__version__}"
        build_date = get_build_date()
        if build_date:
            title += f" ({build_date})"

        # Add current tab path
        tab = self._tab_manager.get_current_tab()
        if tab:
            title += f" - {tab.current_path}"

        self.setWindowTitle(title)

    # === Updates ===

    def _check_for_updates(self):
        """Check for updates in background."""
        try:
            self._update_thread = check_for_updates_async(self._on_update_check_complete)
            _logger.debug("Update check thread started")
        except Exception as e:
            _logger.error(f"Failed to start update check: {e}", exc_info=True)

    def _manual_check_for_updates(self):
        """Manually check for updates."""
        self._update_thread = check_for_updates_async(self._on_manual_update_check_complete)

    def _on_update_check_complete(self, release_info: "ReleaseInfo | None"):
        """Handle automatic update check result."""
        if release_info:
            self._show_update_notification(release_info)

    def _on_manual_update_check_complete(self, release_info: "ReleaseInfo | None"):
        """Handle manual update check result."""
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

    # === Settings Persistence ===

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

        # View mode for initial tab
        view_mode = self._settings.load_view_mode()
        tab = self._tab_manager.get_current_tab()
        if tab:
            tab.set_view_mode(view_mode)
            _logger.debug(f"View mode set to: {view_mode}")

        _logger.debug("_load_settings completed")

    def _save_settings(self):
        """Save current settings."""
        self._settings.save_window_geometry(self.saveGeometry())

    def closeEvent(self, event):
        """Save settings and cleanup on close."""
        self._save_settings()

        # Cleanup all tabs
        for tab in self._tab_manager.get_all_tabs():
            tab.cleanup()

        super().closeEvent(event)

    # === Serialization for Session ===

    def serialize_window(self) -> dict:
        """Serialize window state for session persistence."""
        import base64

        return {
            "geometry": base64.b64encode(self.saveGeometry().data()).decode(),
            "tabs": self._tab_manager.serialize_all(),
            "active_tab": self._tab_manager.get_active_tab_index(),
        }

    def restore_from_session(self, data: dict):
        """Restore window state from session data."""
        from PySide6.QtWidgets import QFileIconProvider
        import base64

        # Restore geometry
        geometry_b64 = data.get("geometry")
        if geometry_b64:
            geometry_bytes = base64.b64decode(geometry_b64)
            self.restoreGeometry(geometry_bytes)

        # Close default tab (both from manager and tab bar)
        while self._tab_manager.count() > 0:
            self._tab_manager.close_tab(0)
        while self._tab_bar.count() > 0:
            self._tab_bar.removeTab(0)

        # Restore tabs
        tabs_data = data.get("tabs", [])
        icon_provider = QFileIconProvider()
        folder_icon = icon_provider.icon(QFileIconProvider.IconType.Folder)

        for tab_data in tabs_data:
            index = self._tab_manager.merge_tab(tab_data)
            # Manually add to tab bar since signal might not work during restore
            tab = self._tab_manager.get_tab(index)
            if tab and self._tab_bar.count() <= index:
                self._tab_bar.addTab(folder_icon, tab.get_tab_title())
                self._tab_bar.setTabToolTip(index, tab.get_tab_tooltip())
                self._connect_tab_content_signals(tab)

        # Restore active tab
        active_tab = data.get("active_tab", 0)
        if 0 <= active_tab < self._tab_manager.count():
            self._tab_manager.switch_to_tab(active_tab)
            self._tab_bar.setCurrentIndex(active_tab)
