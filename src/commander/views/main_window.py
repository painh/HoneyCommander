"""Main window with tab support and 3-panel layout."""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QStatusBar,
    QStackedWidget,
    QSpacerItem,
    QSizePolicy,
)

from commander.widgets.tab_bar import CommanderTabBar
from commander.core.tab_manager import TabManager
from commander.core.file_operations import FileOperations
from commander.utils.settings import Settings
from commander.utils.i18n import tr
from commander.utils.update_checker import check_for_updates_async, ReleaseInfo
from commander.utils.logger import get_logger
from commander.views.main_window_tabs import MainWindowTabsMixin
from commander.views.main_window_menu import MainWindowMenuMixin
from commander.views.main_window_file_ops import MainWindowFileOpsMixin

_logger = get_logger()


class MainWindow(MainWindowTabsMixin, MainWindowMenuMixin, MainWindowFileOpsMixin, QMainWindow):
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
        tab_bar_layout.setSpacing(0)

        # Tab bar (no stretch - stays compact)
        _logger.debug("_setup_ui: Creating tab bar...")
        self._tab_bar = CommanderTabBar()
        tab_bar_layout.addWidget(self._tab_bar)

        # New tab button with shortcut hint (right next to tabs)
        # Determine shortcut key based on platform
        shortcut_key = "Cmd+T" if sys.platform == "darwin" else "Ctrl+T"

        self._new_tab_btn = QPushButton(f"+  {shortcut_key}")
        self._new_tab_btn.setToolTip(f"New Tab ({shortcut_key})")
        self._new_tab_btn.setStyleSheet("""
            QPushButton {
                background: #3c3c3c;
                color: #888888;
                border: 1px solid #555555;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 12px;
                margin-left: 2px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #454545;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #2d2d2d;
            }
        """)
        self._new_tab_btn.clicked.connect(self._create_new_tab)
        tab_bar_layout.addWidget(self._new_tab_btn)

        # Spacer to push everything to the left
        tab_bar_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )

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
