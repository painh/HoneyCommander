"""Network drives panel for the sidebar."""

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from commander.core.network import (
    ConnectionConfig,
    ConnectionManager,
    ConnectionState,
    CredentialManager,
)
from commander.utils.settings import Settings
from commander.widgets.network_connect_dialog import NetworkConnectDialog

_logger = logging.getLogger(__name__)


class NetworkDrivePanel(QWidget):
    """Panel showing network drive connections."""

    # Signals
    connection_selected = Signal(str, str)  # connection_id, path
    path_selected = Signal(str, str)  # connection_id, path

    def __init__(self, parent=None):
        """Initialize the panel."""
        super().__init__(parent)
        self._settings = Settings()
        self._connection_manager = ConnectionManager(self)

        self._setup_ui()
        self._connect_signals()
        self._load_saved_connections()

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFrameStyle(QFrame.StyledPanel)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 4, 4)

        title = QLabel("Network Drives")
        title.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Add button
        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setToolTip("Add network connection")
        add_btn.clicked.connect(self._show_add_dialog)
        header_layout.addWidget(add_btn)

        layout.addWidget(header)

        # Connection tree
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.itemExpanded.connect(self._on_item_expanded)

        layout.addWidget(self._tree)

        # Set size policy
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.setMaximumHeight(200)

    def _connect_signals(self) -> None:
        """Connect to connection manager signals."""
        self._connection_manager.connection_state_changed.connect(self._on_connection_state_changed)
        self._connection_manager.entries_loaded.connect(self._on_entries_loaded)
        self._connection_manager.error_occurred.connect(self._on_error)

    def _load_saved_connections(self) -> None:
        """Load saved connections from settings."""
        connections = self._settings.load_network_connections()

        for conn_data in connections:
            try:
                config = ConnectionConfig(
                    protocol=conn_data.get("protocol", "smb"),
                    host=conn_data.get("host", ""),
                    port=conn_data.get("port"),
                    share=conn_data.get("share"),
                    username=conn_data.get("username"),
                    display_name=conn_data.get("display_name"),
                    key_file=conn_data.get("key_file"),
                    domain=conn_data.get("domain"),
                    connection_id=conn_data.get("connection_id"),
                )

                if config.connection_id:
                    self._add_connection_item(config)

            except Exception as e:
                _logger.error(f"Failed to load connection: {e}")

    def _add_connection_item(self, config: ConnectionConfig) -> None:
        """Add a connection item to the tree.

        Args:
            config: Connection configuration.
        """
        conn_id = config.connection_id
        if not conn_id:
            return

        # Add to connection manager
        try:
            self._connection_manager.add_connection(conn_id, config)
        except ValueError as e:
            _logger.warning(f"Could not add handler: {e}")

        # Create tree item
        item = QTreeWidgetItem()
        item.setText(0, config.get_display_name())
        item.setData(0, Qt.UserRole, conn_id)
        item.setData(0, Qt.UserRole + 1, "connection")

        # Set icon based on protocol
        if config.protocol == "smb":
            item.setIcon(0, QIcon.fromTheme("network-server"))
        else:
            item.setIcon(0, QIcon.fromTheme("network-server"))

        # Make it expandable
        item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

        self._tree.addTopLevelItem(item)
        self._update_item_state(item, ConnectionState.DISCONNECTED)

    def _update_item_state(self, item: QTreeWidgetItem, state: ConnectionState) -> None:
        """Update item appearance based on connection state.

        Args:
            item: Tree widget item.
            state: Connection state.
        """
        # Update icon or text style based on state
        text = item.text(0)

        # Remove any existing state suffix
        for suffix in [" (Connecting...)", " (Error)", " (Connected)"]:
            if text.endswith(suffix):
                text = text[: -len(suffix)]

        if state == ConnectionState.CONNECTING:
            item.setText(0, f"{text} (Connecting...)")
        elif state == ConnectionState.ERROR:
            item.setText(0, f"{text} (Error)")
        elif state == ConnectionState.CONNECTED:
            # Show as connected without suffix for cleaner look
            item.setText(0, text)

    def _show_add_dialog(self) -> None:
        """Show dialog to add new connection."""
        dialog = NetworkConnectDialog(self)
        if dialog.exec():
            config = dialog.get_config()
            password = dialog.get_password()
            save_password = dialog.should_save_password()

            # Save connection to settings
            config_dict = {
                "protocol": config.protocol,
                "host": config.host,
                "port": config.port,
                "share": config.share,
                "username": config.username,
                "display_name": config.display_name,
                "key_file": config.key_file,
                "domain": config.domain,
            }

            conn_id = self._settings.add_network_connection(config_dict)
            config.connection_id = conn_id

            # Save password if requested
            if save_password and password and config.username:
                CredentialManager.save_credential(conn_id, config.username, password)

            # Add to UI
            self._add_connection_item(config)

            # Auto-connect
            self._connect_to(conn_id, password)

    def _show_edit_dialog(self, item: QTreeWidgetItem) -> None:
        """Show dialog to edit a connection."""
        conn_id = item.data(0, Qt.UserRole)
        if not conn_id:
            return

        # Get current config from settings
        config_dict = self._settings.get_network_connection(conn_id)
        if not config_dict:
            return

        config = ConnectionConfig(
            protocol=config_dict.get("protocol", "smb"),
            host=config_dict.get("host", ""),
            port=config_dict.get("port"),
            share=config_dict.get("share"),
            username=config_dict.get("username"),
            display_name=config_dict.get("display_name"),
            key_file=config_dict.get("key_file"),
            domain=config_dict.get("domain"),
            connection_id=conn_id,
        )

        dialog = NetworkConnectDialog(self, config, conn_id)
        if dialog.exec():
            new_config = dialog.get_config()
            password = dialog.get_password()
            save_password = dialog.should_save_password()

            # Update settings
            new_config_dict = {
                "protocol": new_config.protocol,
                "host": new_config.host,
                "port": new_config.port,
                "share": new_config.share,
                "username": new_config.username,
                "display_name": new_config.display_name,
                "key_file": new_config.key_file,
                "domain": new_config.domain,
            }

            self._settings.update_network_connection(conn_id, new_config_dict)

            # Update password
            if save_password and password and new_config.username:
                CredentialManager.save_credential(conn_id, new_config.username, password)

            # Update UI
            item.setText(0, new_config.get_display_name())

            # Reconnect if currently connected
            if self._connection_manager.is_connected(conn_id):
                self._connection_manager.disconnect_async(conn_id)
                self._connect_to(conn_id, password)

    def _show_context_menu(self, pos) -> None:
        """Show context menu for tree item."""
        item = self._tree.itemAt(pos)
        if not item:
            return

        item_type = item.data(0, Qt.UserRole + 1)
        if item_type != "connection":
            return

        conn_id = item.data(0, Qt.UserRole)
        is_connected = self._connection_manager.is_connected(conn_id)

        menu = QMenu(self)

        if is_connected:
            disconnect_action = QAction("Disconnect", self)
            disconnect_action.triggered.connect(lambda: self._disconnect_from(conn_id))
            menu.addAction(disconnect_action)
        else:
            connect_action = QAction("Connect", self)
            connect_action.triggered.connect(lambda: self._connect_to(conn_id))
            menu.addAction(connect_action)

        menu.addSeparator()

        edit_action = QAction("Edit...", self)
        edit_action.triggered.connect(lambda: self._show_edit_dialog(item))
        menu.addAction(edit_action)

        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self._remove_connection(item))
        menu.addAction(remove_action)

        menu.exec(self._tree.mapToGlobal(pos))

    def _connect_to(self, conn_id: str, password: str | None = None) -> None:
        """Connect to a network drive.

        Args:
            conn_id: Connection ID.
            password: Optional password.
        """
        self._connection_manager.connect_async(conn_id, password)

    def _disconnect_from(self, conn_id: str) -> None:
        """Disconnect from a network drive.

        Args:
            conn_id: Connection ID.
        """
        # Clear children from tree
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and item.data(0, Qt.UserRole) == conn_id:
                # Remove all children
                while item.childCount() > 0:
                    item.removeChild(item.child(0))
                break

        self._connection_manager.disconnect_async(conn_id)

    def _remove_connection(self, item: QTreeWidgetItem) -> None:
        """Remove a connection.

        Args:
            item: Tree widget item.
        """
        conn_id = item.data(0, Qt.UserRole)
        if not conn_id:
            return

        result = QMessageBox.question(
            self,
            "Remove Connection",
            f"Are you sure you want to remove this connection?\n\n{item.text(0)}",
            QMessageBox.Yes | QMessageBox.No,
        )

        if result != QMessageBox.Yes:
            return

        # Remove from connection manager
        self._connection_manager.remove_connection(conn_id)

        # Remove from settings
        self._settings.remove_network_connection(conn_id)

        # Remove from keychain
        CredentialManager.delete_credential(conn_id)

        # Remove from tree
        index = self._tree.indexOfTopLevelItem(item)
        if index >= 0:
            self._tree.takeTopLevelItem(index)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle item double click."""
        item_type = item.data(0, Qt.UserRole + 1)
        conn_id = item.data(0, Qt.UserRole)

        if item_type == "connection":
            # Connect if not connected
            if not self._connection_manager.is_connected(conn_id):
                self._connect_to(conn_id)
            else:
                # Emit selection signal
                self.connection_selected.emit(conn_id, "/")

        elif item_type == "folder":
            path = item.data(0, Qt.UserRole + 2)
            # Get parent connection ID
            parent = item.parent()
            while parent:
                if parent.data(0, Qt.UserRole + 1) == "connection":
                    conn_id = parent.data(0, Qt.UserRole)
                    break
                parent = parent.parent()

            if conn_id:
                self.path_selected.emit(conn_id, path)

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Handle item expansion."""
        item_type = item.data(0, Qt.UserRole + 1)

        if item_type == "connection":
            conn_id = item.data(0, Qt.UserRole)
            if self._connection_manager.is_connected(conn_id):
                # Load root entries
                self._connection_manager.list_entries_async(conn_id, "/")

        elif item_type == "folder":
            # Get connection ID and path
            path = item.data(0, Qt.UserRole + 2)
            parent = item.parent()
            conn_id = None

            while parent:
                if parent.data(0, Qt.UserRole + 1) == "connection":
                    conn_id = parent.data(0, Qt.UserRole)
                    break
                parent = parent.parent()

            if conn_id and path:
                self._connection_manager.list_entries_async(conn_id, path)

    def _on_connection_state_changed(self, conn_id: str, state: ConnectionState) -> None:
        """Handle connection state change."""
        # Find the item
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and item.data(0, Qt.UserRole) == conn_id:
                self._update_item_state(item, state)

                # If connected, load root entries
                if state == ConnectionState.CONNECTED:
                    self._connection_manager.list_entries_async(conn_id, "/")

                break

    def _on_entries_loaded(self, conn_id: str, path: str, entries: list) -> None:
        """Handle loaded entries."""
        # Find parent item
        parent_item = None

        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and item.data(0, Qt.UserRole) == conn_id:
                if path == "/" or path == "":
                    parent_item = item
                else:
                    # Find folder item
                    parent_item = self._find_folder_item(item, path)
                break

        if not parent_item:
            return

        # Clear existing children
        while parent_item.childCount() > 0:
            parent_item.removeChild(parent_item.child(0))

        # Add new entries (only directories for tree view)
        for entry in entries:
            if entry.is_dir:
                child = QTreeWidgetItem()
                child.setText(0, entry.name)
                child.setIcon(0, QIcon.fromTheme("folder"))
                child.setData(0, Qt.UserRole, conn_id)
                child.setData(0, Qt.UserRole + 1, "folder")
                child.setData(0, Qt.UserRole + 2, entry.path)
                child.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
                parent_item.addChild(child)

    def _find_folder_item(self, parent: QTreeWidgetItem, path: str) -> QTreeWidgetItem | None:
        """Find folder item by path.

        Args:
            parent: Parent item.
            path: Path to find.

        Returns:
            Item if found, None otherwise.
        """
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child:
                child_path = child.data(0, Qt.UserRole + 2)
                if child_path == path:
                    return child
                # Recurse
                found = self._find_folder_item(child, path)
                if found:
                    return found

        return None

    def _on_error(self, conn_id: str, error: str) -> None:
        """Handle error."""
        _logger.error(f"Network error ({conn_id}): {error}")

        # Show error briefly in status or as tooltip
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item and item.data(0, Qt.UserRole) == conn_id:
                item.setToolTip(0, f"Error: {error}")
                break

    @property
    def connection_manager(self) -> ConnectionManager:
        """Get the connection manager."""
        return self._connection_manager

    def cleanup(self) -> None:
        """Clean up connections."""
        self._connection_manager.cleanup()
