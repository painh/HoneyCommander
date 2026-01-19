"""SFTP protocol handler using paramiko."""

import logging
import stat
from datetime import datetime
from pathlib import Path

from .base import ConnectionConfig, ConnectionState, NetworkEntry, NetworkHandler

_logger = logging.getLogger(__name__)

# Try to import paramiko
try:
    import paramiko

    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    _logger.warning("paramiko not installed, SFTP support unavailable")


class SFTPHandler(NetworkHandler):
    """Handler for SFTP protocol.

    Uses paramiko library for SSH/SFTP access.
    """

    def __init__(self, config: ConnectionConfig):
        """Initialize SFTP handler.

        Args:
            config: Connection configuration with host and optional key_file.
        """
        super().__init__(config)
        self._transport: "paramiko.Transport | None" = None
        self._sftp: "paramiko.SFTPClient | None" = None

    @staticmethod
    def is_available() -> bool:
        """Check if SFTP support is available."""
        return PARAMIKO_AVAILABLE

    def connect(self, password: str | None = None) -> bool:
        """Connect to SFTP server.

        Args:
            password: Password for authentication.
                     If key_file is configured, this is the key passphrase.

        Returns:
            True if connected successfully.
        """
        if not PARAMIKO_AVAILABLE:
            self._set_state(ConnectionState.ERROR, "paramiko library not installed")
            return False

        self._set_state(ConnectionState.CONNECTING)

        try:
            # Create transport
            host = self.config.host
            port = self.config.get_port()

            self._transport = paramiko.Transport((host, port))

            # Authenticate
            username = self.config.username or ""

            if self.config.key_file:
                # Key-based authentication
                key_path = Path(self.config.key_file).expanduser()
                if not key_path.exists():
                    raise FileNotFoundError(f"Key file not found: {key_path}")

                # Try different key types
                pkey = None
                key_types = [
                    paramiko.RSAKey,
                    paramiko.Ed25519Key,
                    paramiko.ECDSAKey,
                    paramiko.DSSKey,
                ]

                for key_class in key_types:
                    try:
                        pkey = key_class.from_private_key_file(str(key_path), password=password)
                        break
                    except paramiko.SSHException:
                        continue

                if pkey is None:
                    raise ValueError("Could not load private key")

                self._transport.connect(username=username, pkey=pkey)
            else:
                # Password authentication
                self._transport.connect(username=username, password=password or "")

            # Create SFTP client
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)

            self._set_state(ConnectionState.CONNECTED)
            _logger.info(f"Connected to SFTP: {host}:{port}")
            return True

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"SFTP connection failed: {error_msg}")
            self._set_state(ConnectionState.ERROR, error_msg)
            self._cleanup()
            return False

    def _cleanup(self) -> None:
        """Clean up connections."""
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None

        if self._transport:
            try:
                self._transport.close()
            except Exception:
                pass
            self._transport = None

    def disconnect(self) -> None:
        """Disconnect from SFTP server."""
        self._cleanup()
        self._set_state(ConnectionState.DISCONNECTED)
        _logger.info(f"Disconnected from SFTP: {self.config.host}")

    def list_entries(self, remote_path: str = "/") -> list[NetworkEntry]:
        """List entries in a remote directory.

        Args:
            remote_path: Path on the remote server.

        Returns:
            List of NetworkEntry objects.
        """
        if not self.is_connected or not self._sftp:
            raise ConnectionError("Not connected to SFTP server")

        # Normalize path
        remote_path = remote_path or "/"
        if not remote_path.startswith("/"):
            remote_path = "/" + remote_path

        entries = []

        try:
            for attr in self._sftp.listdir_attr(remote_path):
                try:
                    is_dir = stat.S_ISDIR(attr.st_mode)

                    # Get modified time
                    mtime = None
                    if attr.st_mtime:
                        mtime = datetime.fromtimestamp(attr.st_mtime)

                    # Build full path
                    full_path = f"{remote_path.rstrip('/')}/{attr.filename}"

                    # Get permissions string
                    perms = stat.filemode(attr.st_mode)

                    entry = NetworkEntry(
                        name=attr.filename,
                        path=full_path,
                        is_dir=is_dir,
                        size=attr.st_size if not is_dir else 0,
                        modified_time=mtime,
                        permissions=perms,
                    )
                    entries.append(entry)
                except Exception as e:
                    _logger.warning(f"Failed to process {attr.filename}: {e}")

        except PermissionError:
            raise
        except FileNotFoundError:
            raise
        except IOError as e:
            if "No such file" in str(e):
                raise FileNotFoundError(remote_path)
            raise ConnectionError(f"Failed to list directory: {e}")
        except Exception as e:
            _logger.error(f"Failed to list {remote_path}: {e}")
            raise ConnectionError(f"Failed to list directory: {e}")

        return entries

    def read_file(self, remote_path: str) -> bytes:
        """Read file contents.

        Args:
            remote_path: Path to the file.

        Returns:
            File contents as bytes.
        """
        if not self.is_connected or not self._sftp:
            raise ConnectionError("Not connected to SFTP server")

        try:
            with self._sftp.open(remote_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            raise
        except PermissionError:
            raise
        except IOError as e:
            if "No such file" in str(e):
                raise FileNotFoundError(remote_path)
            raise ConnectionError(f"Failed to read file: {e}")

    def write_file(self, remote_path: str, data: bytes) -> bool:
        """Write data to a file.

        Args:
            remote_path: Path to the file.
            data: Data to write.

        Returns:
            True if successful.
        """
        if not self.is_connected or not self._sftp:
            raise ConnectionError("Not connected to SFTP server")

        try:
            with self._sftp.open(remote_path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            _logger.error(f"Failed to write file: {e}")
            return False

    def mkdir(self, remote_path: str) -> bool:
        """Create a directory.

        Args:
            remote_path: Path to create.

        Returns:
            True if successful.
        """
        if not self.is_connected or not self._sftp:
            raise ConnectionError("Not connected to SFTP server")

        try:
            self._sftp.mkdir(remote_path)
            return True
        except Exception as e:
            _logger.error(f"Failed to create directory: {e}")
            return False

    def delete(self, remote_path: str) -> bool:
        """Delete a file or directory.

        Args:
            remote_path: Path to delete.

        Returns:
            True if successful.
        """
        if not self.is_connected or not self._sftp:
            raise ConnectionError("Not connected to SFTP server")

        try:
            # Check if it's a directory
            attr = self._sftp.stat(remote_path)
            if stat.S_ISDIR(attr.st_mode):
                # Recursively delete directory contents
                self._rmdir_recursive(remote_path)
            else:
                self._sftp.remove(remote_path)
            return True
        except Exception as e:
            _logger.error(f"Failed to delete: {e}")
            return False

    def _rmdir_recursive(self, path: str) -> None:
        """Recursively delete a directory."""
        if not self._sftp:
            return

        for attr in self._sftp.listdir_attr(path):
            full_path = f"{path}/{attr.filename}"
            if stat.S_ISDIR(attr.st_mode):
                self._rmdir_recursive(full_path)
            else:
                self._sftp.remove(full_path)

        self._sftp.rmdir(path)

    def rename(self, old_path: str, new_path: str) -> bool:
        """Rename/move a file or directory.

        Args:
            old_path: Current path.
            new_path: New path.

        Returns:
            True if successful.
        """
        if not self.is_connected or not self._sftp:
            raise ConnectionError("Not connected to SFTP server")

        try:
            self._sftp.rename(old_path, new_path)
            return True
        except Exception as e:
            _logger.error(f"Failed to rename: {e}")
            return False

    def download(
        self,
        remote_path: str,
        local_path: Path,
        progress_callback=None,
    ) -> bool:
        """Download a file.

        Args:
            remote_path: Path on the remote server.
            local_path: Local destination path.
            progress_callback: Optional progress callback.

        Returns:
            True if successful.
        """
        if not self.is_connected or not self._sftp:
            raise ConnectionError("Not connected to SFTP server")

        try:
            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Create progress callback wrapper
            def sftp_callback(bytes_transferred: int, total: int) -> None:
                if progress_callback:
                    progress_callback(bytes_transferred, total)

            # Download with progress
            self._sftp.get(
                remote_path,
                str(local_path),
                callback=sftp_callback if progress_callback else None,
            )

            return True
        except Exception as e:
            _logger.error(f"Failed to download: {e}")
            return False

    def upload(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback=None,
    ) -> bool:
        """Upload a file.

        Args:
            local_path: Local file path.
            remote_path: Destination path on the remote server.
            progress_callback: Optional progress callback.

        Returns:
            True if successful.
        """
        if not self.is_connected or not self._sftp:
            raise ConnectionError("Not connected to SFTP server")

        try:
            # Create progress callback wrapper
            def sftp_callback(bytes_transferred: int, total: int) -> None:
                if progress_callback:
                    progress_callback(bytes_transferred, total)

            # Upload with progress
            self._sftp.put(
                str(local_path),
                remote_path,
                callback=sftp_callback if progress_callback else None,
            )

            return True
        except Exception as e:
            _logger.error(f"Failed to upload: {e}")
            return False

    def exists(self, remote_path: str) -> bool:
        """Check if a path exists.

        Args:
            remote_path: Path to check.

        Returns:
            True if exists.
        """
        if not self.is_connected or not self._sftp:
            return False

        try:
            self._sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
        except IOError:
            return False

    def is_dir(self, remote_path: str) -> bool:
        """Check if a path is a directory.

        Args:
            remote_path: Path to check.

        Returns:
            True if directory.
        """
        if not self.is_connected or not self._sftp:
            return False

        try:
            attr = self._sftp.stat(remote_path)
            return stat.S_ISDIR(attr.st_mode)
        except Exception:
            return False
