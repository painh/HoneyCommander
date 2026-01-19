"""Tab management mixin for main window."""

from __future__ import annotations

from pathlib import Path


class MainWindowTabsMixin:
    """Mixin providing tab management for main window."""

    # Expected from main class
    _tab_bar: object
    _tab_manager: object
    _status_bar: object

    def _connect_tab_signals(self):
        """Connect tab-related signals."""
        from commander.core.undo_manager import get_undo_manager

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

    def _connect_tab_content_signals(self, tab):
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

    def _on_current_tab_changed(self, index: int, tab):
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
