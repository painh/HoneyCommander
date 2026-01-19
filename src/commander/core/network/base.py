"""Base classes for network protocol handlers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable


class ConnectionState(Enum):
    """Network connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class NetworkEntry:
    """Represents a file or directory on a network share."""

    name: str
    path: str
    is_dir: bool
    size: int = 0
    modified_time: datetime | None = None
    permissions: str | None = None

    @property
    def is_file(self) -> bool:
        """Check if entry is a file."""
        return not self.is_dir


@dataclass
class ConnectionConfig:
    """Network connection configuration."""

    protocol: str  # "smb" or "sftp"
    host: str
    port: int | None = None
    share: str | None = None  # SMB share name
    username: str | None = None
    display_name: str | None = None
    connection_id: str | None = None
    # SFTP specific
    key_file: str | None = None
    # SMB specific
    domain: str | None = None

    def get_display_name(self) -> str:
        """Get display name for this connection."""
        if self.display_name:
            return self.display_name
        if self.protocol == "smb" and self.share:
            return f"//{self.host}/{self.share}"
        return f"{self.protocol}://{self.host}"

    def get_default_port(self) -> int:
        """Get default port for the protocol."""
        if self.protocol == "sftp":
            return 22
        elif self.protocol == "smb":
            return 445
        return 0

    def get_port(self) -> int:
        """Get port, using default if not specified."""
        return self.port if self.port is not None else self.get_default_port()


ProgressCallback = Callable[[int, int], None]  # current, total


class NetworkHandler(ABC):
    """Abstract base class for network protocol handlers.

    This class defines the interface for network file system operations.
    Implementations should handle protocol-specific details while
    providing a consistent interface for the application.
    """

    def __init__(self, config: ConnectionConfig):
        """Initialize the handler with connection configuration.

        Args:
            config: Connection configuration.
        """
        self.config = config
        self._state = ConnectionState.DISCONNECTED
        self._error_message: str | None = None

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def error_message(self) -> str | None:
        """Get last error message, if any."""
        return self._error_message

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._state == ConnectionState.CONNECTED

    def _set_state(self, state: ConnectionState, error: str | None = None) -> None:
        """Set connection state and optional error message."""
        self._state = state
        self._error_message = error

    @abstractmethod
    def connect(self, password: str | None = None) -> bool:
        """Connect to the server.

        Args:
            password: Password for authentication. If None, will try
                     key-based auth (SFTP) or anonymous access.

        Returns:
            True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the server."""
        pass

    @abstractmethod
    def list_entries(self, remote_path: str = "/") -> list[NetworkEntry]:
        """List entries in a remote directory.

        Args:
            remote_path: Path on the remote server.

        Returns:
            List of NetworkEntry objects.

        Raises:
            ConnectionError: If not connected.
            PermissionError: If access denied.
            FileNotFoundError: If path doesn't exist.
        """
        pass

    @abstractmethod
    def read_file(self, remote_path: str) -> bytes:
        """Read file contents from the remote server.

        Args:
            remote_path: Path to the file on the remote server.

        Returns:
            File contents as bytes.

        Raises:
            ConnectionError: If not connected.
            FileNotFoundError: If file doesn't exist.
        """
        pass

    @abstractmethod
    def write_file(self, remote_path: str, data: bytes) -> bool:
        """Write data to a file on the remote server.

        Args:
            remote_path: Path to the file on the remote server.
            data: Data to write.

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def mkdir(self, remote_path: str) -> bool:
        """Create a directory on the remote server.

        Args:
            remote_path: Path to create.

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def delete(self, remote_path: str) -> bool:
        """Delete a file or directory on the remote server.

        Args:
            remote_path: Path to delete.

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def rename(self, old_path: str, new_path: str) -> bool:
        """Rename/move a file or directory.

        Args:
            old_path: Current path.
            new_path: New path.

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def download(
        self,
        remote_path: str,
        local_path: Path,
        progress_callback: ProgressCallback | None = None,
    ) -> bool:
        """Download a file from the remote server.

        Args:
            remote_path: Path on the remote server.
            local_path: Local destination path.
            progress_callback: Optional callback for progress updates.

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def upload(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback: ProgressCallback | None = None,
    ) -> bool:
        """Upload a file to the remote server.

        Args:
            local_path: Local file path.
            remote_path: Destination path on the remote server.
            progress_callback: Optional callback for progress updates.

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def exists(self, remote_path: str) -> bool:
        """Check if a path exists on the remote server.

        Args:
            remote_path: Path to check.

        Returns:
            True if exists, False otherwise.
        """
        pass

    @abstractmethod
    def is_dir(self, remote_path: str) -> bool:
        """Check if a path is a directory.

        Args:
            remote_path: Path to check.

        Returns:
            True if directory, False otherwise.
        """
        pass

    def get_entry(self, remote_path: str) -> NetworkEntry | None:
        """Get entry information for a specific path.

        Args:
            remote_path: Path to get info for.

        Returns:
            NetworkEntry if exists, None otherwise.
        """
        if not self.exists(remote_path):
            return None

        # Default implementation - subclasses can override for efficiency
        parent = "/".join(remote_path.rstrip("/").split("/")[:-1]) or "/"
        name = remote_path.rstrip("/").split("/")[-1]

        try:
            entries = self.list_entries(parent)
            for entry in entries:
                if entry.name == name:
                    return entry
        except (ConnectionError, PermissionError, FileNotFoundError):
            pass

        return None
