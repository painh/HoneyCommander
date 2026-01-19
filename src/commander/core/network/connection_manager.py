"""Network connection manager with async support."""

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from .base import ConnectionConfig, ConnectionState, NetworkHandler
from .credentials import CredentialManager
from .sftp_handler import SFTPHandler
from .smb_handler import SMBHandler

_logger = logging.getLogger(__name__)


class ConnectionWorker(QThread):
    """Worker thread for async network operations."""

    # Signals
    connected = Signal(bool, str)  # success, error_message
    disconnected = Signal()
    entries_loaded = Signal(str, list)  # path, list of NetworkEntry
    operation_complete = Signal(bool, str)  # success, error_message
    progress = Signal(int, int)  # current, total
    error = Signal(str)  # error_message

    def __init__(
        self,
        handler: NetworkHandler,
        operation: str,
        **kwargs: Any,
    ):
        """Initialize worker.

        Args:
            handler: Network handler to use.
            operation: Operation to perform (connect, list, download, upload, etc.)
            **kwargs: Operation-specific arguments.
        """
        super().__init__()
        self._handler = handler
        self._operation = operation
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the operation."""
        self._cancelled = True

    def run(self) -> None:
        """Execute the operation."""
        try:
            if self._operation == "connect":
                password = self._kwargs.get("password")
                success = self._handler.connect(password)
                error_msg = self._handler.error_message if not success else ""
                self.connected.emit(success, error_msg or "")

            elif self._operation == "disconnect":
                self._handler.disconnect()
                self.disconnected.emit()

            elif self._operation == "list":
                path = self._kwargs.get("path", "/")
                entries = self._handler.list_entries(path)
                self.entries_loaded.emit(path, entries)

            elif self._operation == "download":
                remote_path = self._kwargs.get("remote_path")
                local_path = self._kwargs.get("local_path")

                def progress_cb(current: int, total: int) -> None:
                    if not self._cancelled:
                        self.progress.emit(current, total)

                success = self._handler.download(remote_path, local_path, progress_cb)
                self.operation_complete.emit(success, "" if success else "Download failed")

            elif self._operation == "upload":
                local_path = self._kwargs.get("local_path")
                remote_path = self._kwargs.get("remote_path")

                def progress_cb(current: int, total: int) -> None:
                    if not self._cancelled:
                        self.progress.emit(current, total)

                success = self._handler.upload(local_path, remote_path, progress_cb)
                self.operation_complete.emit(success, "" if success else "Upload failed")

            elif self._operation == "delete":
                remote_path = self._kwargs.get("remote_path")
                success = self._handler.delete(remote_path)
                self.operation_complete.emit(success, "" if success else "Delete failed")

            elif self._operation == "mkdir":
                remote_path = self._kwargs.get("remote_path")
                success = self._handler.mkdir(remote_path)
                self.operation_complete.emit(success, "" if success else "Create folder failed")

            elif self._operation == "rename":
                old_path = self._kwargs.get("old_path")
                new_path = self._kwargs.get("new_path")
                success = self._handler.rename(old_path, new_path)
                self.operation_complete.emit(success, "" if success else "Rename failed")

        except Exception as e:
            _logger.error(f"Worker error: {e}")
            self.error.emit(str(e))


class ConnectionManager(QObject):
    """Manages network connections with async support.

    This class provides a central point for managing multiple network
    connections with proper threading for non-blocking operations.
    """

    # Signals
    connection_state_changed = Signal(str, ConnectionState)  # conn_id, state
    entries_loaded = Signal(str, str, list)  # conn_id, path, entries
    operation_progress = Signal(str, int, int)  # conn_id, current, total
    operation_complete = Signal(str, bool, str)  # conn_id, success, error
    error_occurred = Signal(str, str)  # conn_id, error_message

    def __init__(self, parent: QObject | None = None):
        """Initialize connection manager."""
        super().__init__(parent)
        self._handlers: dict[str, NetworkHandler] = {}
        self._workers: dict[str, ConnectionWorker] = {}

    def create_handler(self, config: ConnectionConfig) -> NetworkHandler:
        """Create a handler for the given configuration.

        Args:
            config: Connection configuration.

        Returns:
            Appropriate NetworkHandler subclass.

        Raises:
            ValueError: If protocol is not supported.
        """
        protocol = config.protocol.lower()

        if protocol == "smb":
            if not SMBHandler.is_available():
                raise ValueError("SMB support not available (install smbprotocol)")
            return SMBHandler(config)

        elif protocol == "sftp":
            if not SFTPHandler.is_available():
                raise ValueError("SFTP support not available (install paramiko)")
            return SFTPHandler(config)

        else:
            raise ValueError(f"Unsupported protocol: {protocol}")

    def add_connection(self, connection_id: str, config: ConnectionConfig) -> None:
        """Add a connection configuration.

        Args:
            connection_id: Unique identifier for the connection.
            config: Connection configuration.
        """
        config.connection_id = connection_id
        handler = self.create_handler(config)
        self._handlers[connection_id] = handler
        _logger.info(f"Added connection: {connection_id}")

    def remove_connection(self, connection_id: str) -> None:
        """Remove a connection.

        Args:
            connection_id: ID of the connection to remove.
        """
        if connection_id in self._handlers:
            handler = self._handlers[connection_id]
            if handler.is_connected:
                handler.disconnect()
            del self._handlers[connection_id]

        if connection_id in self._workers:
            worker = self._workers[connection_id]
            worker.cancel()
            worker.wait()
            del self._workers[connection_id]

        _logger.info(f"Removed connection: {connection_id}")

    def get_handler(self, connection_id: str) -> NetworkHandler | None:
        """Get handler for a connection.

        Args:
            connection_id: ID of the connection.

        Returns:
            Handler if exists, None otherwise.
        """
        return self._handlers.get(connection_id)

    def get_state(self, connection_id: str) -> ConnectionState:
        """Get connection state.

        Args:
            connection_id: ID of the connection.

        Returns:
            Connection state.
        """
        handler = self._handlers.get(connection_id)
        if handler:
            return handler.state
        return ConnectionState.DISCONNECTED

    def is_connected(self, connection_id: str) -> bool:
        """Check if a connection is active.

        Args:
            connection_id: ID of the connection.

        Returns:
            True if connected.
        """
        handler = self._handlers.get(connection_id)
        return handler.is_connected if handler else False

    def connect_async(
        self,
        connection_id: str,
        password: str | None = None,
    ) -> None:
        """Connect asynchronously.

        Args:
            connection_id: ID of the connection.
            password: Password for authentication.
        """
        handler = self._handlers.get(connection_id)
        if not handler:
            self.error_occurred.emit(connection_id, "Connection not found")
            return

        # Cancel any existing worker
        self._cancel_worker(connection_id)

        # Try to get password from keychain if not provided
        if password is None:
            password = CredentialManager.get_password(connection_id)

        # Create worker
        worker = ConnectionWorker(handler, "connect", password=password)
        worker.connected.connect(
            lambda success, error: self._on_connected(connection_id, success, error)
        )
        worker.error.connect(lambda error: self.error_occurred.emit(connection_id, error))

        self._workers[connection_id] = worker
        self.connection_state_changed.emit(connection_id, ConnectionState.CONNECTING)
        worker.start()

    def _on_connected(self, connection_id: str, success: bool, error: str) -> None:
        """Handle connection result."""
        handler = self._handlers.get(connection_id)
        if handler:
            state = handler.state
            self.connection_state_changed.emit(connection_id, state)
            if not success and error:
                self.error_occurred.emit(connection_id, error)

    def disconnect_async(self, connection_id: str) -> None:
        """Disconnect asynchronously.

        Args:
            connection_id: ID of the connection.
        """
        handler = self._handlers.get(connection_id)
        if not handler:
            return

        # Cancel any existing worker
        self._cancel_worker(connection_id)

        # Create worker
        worker = ConnectionWorker(handler, "disconnect")
        worker.disconnected.connect(
            lambda: self.connection_state_changed.emit(connection_id, ConnectionState.DISCONNECTED)
        )

        self._workers[connection_id] = worker
        worker.start()

    def list_entries_async(self, connection_id: str, path: str = "/") -> None:
        """List directory entries asynchronously.

        Args:
            connection_id: ID of the connection.
            path: Remote path to list.
        """
        handler = self._handlers.get(connection_id)
        if not handler:
            self.error_occurred.emit(connection_id, "Connection not found")
            return

        if not handler.is_connected:
            self.error_occurred.emit(connection_id, "Not connected")
            return

        # Create worker
        worker = ConnectionWorker(handler, "list", path=path)
        worker.entries_loaded.connect(
            lambda p, entries: self.entries_loaded.emit(connection_id, p, entries)
        )
        worker.error.connect(lambda error: self.error_occurred.emit(connection_id, error))

        # Store with unique key for parallel operations
        worker_key = f"{connection_id}_list_{path}"
        self._workers[worker_key] = worker
        worker.start()

    def download_async(
        self,
        connection_id: str,
        remote_path: str,
        local_path: "Path",
    ) -> None:
        """Download a file asynchronously.

        Args:
            connection_id: ID of the connection.
            remote_path: Path on the remote server.
            local_path: Local destination path.
        """

        handler = self._handlers.get(connection_id)
        if not handler:
            self.error_occurred.emit(connection_id, "Connection not found")
            return

        if not handler.is_connected:
            self.error_occurred.emit(connection_id, "Not connected")
            return

        # Create worker
        worker = ConnectionWorker(
            handler, "download", remote_path=remote_path, local_path=local_path
        )
        worker.progress.connect(
            lambda current, total: self.operation_progress.emit(connection_id, current, total)
        )
        worker.operation_complete.connect(
            lambda success, error: self.operation_complete.emit(connection_id, success, error)
        )
        worker.error.connect(lambda error: self.error_occurred.emit(connection_id, error))

        worker_key = f"{connection_id}_download"
        self._workers[worker_key] = worker
        worker.start()

    def upload_async(
        self,
        connection_id: str,
        local_path: "Path",
        remote_path: str,
    ) -> None:
        """Upload a file asynchronously.

        Args:
            connection_id: ID of the connection.
            local_path: Local file path.
            remote_path: Destination path on the remote server.
        """

        handler = self._handlers.get(connection_id)
        if not handler:
            self.error_occurred.emit(connection_id, "Connection not found")
            return

        if not handler.is_connected:
            self.error_occurred.emit(connection_id, "Not connected")
            return

        # Create worker
        worker = ConnectionWorker(handler, "upload", local_path=local_path, remote_path=remote_path)
        worker.progress.connect(
            lambda current, total: self.operation_progress.emit(connection_id, current, total)
        )
        worker.operation_complete.connect(
            lambda success, error: self.operation_complete.emit(connection_id, success, error)
        )
        worker.error.connect(lambda error: self.error_occurred.emit(connection_id, error))

        worker_key = f"{connection_id}_upload"
        self._workers[worker_key] = worker
        worker.start()

    def _cancel_worker(self, connection_id: str) -> None:
        """Cancel any existing worker for a connection."""
        # Cancel workers with matching connection_id prefix
        to_remove = []
        for key, worker in self._workers.items():
            if key == connection_id or key.startswith(f"{connection_id}_"):
                worker.cancel()
                worker.wait(1000)  # Wait up to 1 second
                to_remove.append(key)

        for key in to_remove:
            del self._workers[key]

    def cleanup(self) -> None:
        """Clean up all connections and workers."""
        # Cancel all workers
        for worker in self._workers.values():
            worker.cancel()
            worker.wait(1000)
        self._workers.clear()

        # Disconnect all handlers
        for handler in self._handlers.values():
            if handler.is_connected:
                try:
                    handler.disconnect()
                except Exception as e:
                    _logger.error(f"Error disconnecting: {e}")
        self._handlers.clear()

        _logger.info("Connection manager cleaned up")
