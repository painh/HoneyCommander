"""Menu and toolbar setup mixin for main window."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QToolBar, QPushButton, QDialog
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from commander.utils.i18n import tr


class MainWindowMenuMixin:
    """Mixin providing menu and toolbar setup for main window."""

    # Expected from main class
    _tab_manager: object
    _settings: object

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
