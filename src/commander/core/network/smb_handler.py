"""SMB/CIFS protocol handler."""

import logging
import stat
from datetime import datetime
from pathlib import Path

from .base import ConnectionConfig, ConnectionState, NetworkEntry, NetworkHandler

_logger = logging.getLogger(__name__)

# Try to import smbclient
try:
    import smbclient
    from smbclient import shutil as smb_shutil
    from smbclient.path import isdir as smb_isdir
    from smbclient.path import exists as smb_exists

    SMB_AVAILABLE = True
except ImportError:
    SMB_AVAILABLE = False
    _logger.warning("smbprotocol not installed, SMB support unavailable")


class SMBHandler(NetworkHandler):
    """Handler for SMB/CIFS protocol.

    Uses smbprotocol library for cross-platform SMB access.
    On Windows, can also use native UNC paths.
    """

    def __init__(self, config: ConnectionConfig):
        """Initialize SMB handler.

        Args:
            config: Connection configuration with host and share.
        """
        super().__init__(config)
        self._registered = False

    @staticmethod
    def is_available() -> bool:
        """Check if SMB support is available."""
        return SMB_AVAILABLE

    def _get_unc_path(self, remote_path: str = "") -> str:
        """Get UNC path for remote location.

        Args:
            remote_path: Path relative to share root.

        Returns:
            Full UNC path.
        """
        # Normalize path separators
        remote_path = remote_path.replace("\\", "/").strip("/")

        # Build UNC path
        host = self.config.host
        share = self.config.share or ""

        if remote_path:
            return f"\\\\{host}\\{share}\\{remote_path}".replace("/", "\\")
        elif share:
            return f"\\\\{host}\\{share}"
        else:
            return f"\\\\{host}"

    def connect(self, password: str | None = None) -> bool:
        """Connect to SMB server.

        Args:
            password: Password for authentication.

        Returns:
            True if connected successfully.
        """
        if not SMB_AVAILABLE:
            self._set_state(ConnectionState.ERROR, "smbprotocol library not installed")
            return False

        self._set_state(ConnectionState.CONNECTING)

        try:
            # Register session with smbclient
            smbclient.register_session(
                server=self.config.host,
                username=self.config.username,
                password=password or "",
                port=self.config.get_port(),
            )
            self._registered = True

            # Test connection by listing the share
            unc_path = self._get_unc_path()
            smbclient.listdir(unc_path)

            self._set_state(ConnectionState.CONNECTED)
            _logger.info(f"Connected to SMB: {self.config.host}/{self.config.share}")
            return True

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"SMB connection failed: {error_msg}")
            self._set_state(ConnectionState.ERROR, error_msg)
            return False

    def disconnect(self) -> None:
        """Disconnect from SMB server."""
        # smbclient doesn't have explicit disconnect
        # Sessions are managed internally
        self._registered = False
        self._set_state(ConnectionState.DISCONNECTED)
        _logger.info(f"Disconnected from SMB: {self.config.host}")

    def list_entries(self, remote_path: str = "/") -> list[NetworkEntry]:
        """List entries in a remote directory.

        Args:
            remote_path: Path on the remote server.

        Returns:
            List of NetworkEntry objects.
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to SMB server")

        unc_path = self._get_unc_path(remote_path)
        entries = []

        try:
            for item in smbclient.scandir(unc_path):
                try:
                    stat_info = item.stat()
                    is_dir = stat.S_ISDIR(stat_info.st_mode)

                    # Get modified time
                    mtime = None
                    if stat_info.st_mtime:
                        mtime = datetime.fromtimestamp(stat_info.st_mtime)

                    # Build relative path
                    rel_path = f"{remote_path.rstrip('/')}/{item.name}"

                    entry = NetworkEntry(
                        name=item.name,
                        path=rel_path,
                        is_dir=is_dir,
                        size=stat_info.st_size if not is_dir else 0,
                        modified_time=mtime,
                    )
                    entries.append(entry)
                except Exception as e:
                    _logger.warning(f"Failed to stat {item.name}: {e}")

        except PermissionError:
            raise
        except FileNotFoundError:
            raise
        except Exception as e:
            _logger.error(f"Failed to list {unc_path}: {e}")
            raise ConnectionError(f"Failed to list directory: {e}")

        return entries

    def read_file(self, remote_path: str) -> bytes:
        """Read file contents.

        Args:
            remote_path: Path to the file.

        Returns:
            File contents as bytes.
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to SMB server")

        unc_path = self._get_unc_path(remote_path)

        try:
            with smbclient.open_file(unc_path, mode="rb") as f:
                return f.read()
        except FileNotFoundError:
            raise
        except PermissionError:
            raise
        except Exception as e:
            raise ConnectionError(f"Failed to read file: {e}")

    def write_file(self, remote_path: str, data: bytes) -> bool:
        """Write data to a file.

        Args:
            remote_path: Path to the file.
            data: Data to write.

        Returns:
            True if successful.
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to SMB server")

        unc_path = self._get_unc_path(remote_path)

        try:
            with smbclient.open_file(unc_path, mode="wb") as f:
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
        if not self.is_connected:
            raise ConnectionError("Not connected to SMB server")

        unc_path = self._get_unc_path(remote_path)

        try:
            smbclient.mkdir(unc_path)
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
        if not self.is_connected:
            raise ConnectionError("Not connected to SMB server")

        unc_path = self._get_unc_path(remote_path)

        try:
            if smb_isdir(unc_path):
                smb_shutil.rmtree(unc_path)
            else:
                smbclient.remove(unc_path)
            return True
        except Exception as e:
            _logger.error(f"Failed to delete: {e}")
            return False

    def rename(self, old_path: str, new_path: str) -> bool:
        """Rename/move a file or directory.

        Args:
            old_path: Current path.
            new_path: New path.

        Returns:
            True if successful.
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to SMB server")

        old_unc = self._get_unc_path(old_path)
        new_unc = self._get_unc_path(new_path)

        try:
            smbclient.rename(old_unc, new_unc)
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
        if not self.is_connected:
            raise ConnectionError("Not connected to SMB server")

        unc_path = self._get_unc_path(remote_path)

        try:
            # Get file size for progress
            stat_info = smbclient.stat(unc_path)
            total_size = stat_info.st_size

            # Ensure parent directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy with progress
            bytes_copied = 0
            chunk_size = 1024 * 1024  # 1MB chunks

            with smbclient.open_file(unc_path, mode="rb") as src:
                with open(local_path, "wb") as dst:
                    while True:
                        chunk = src.read(chunk_size)
                        if not chunk:
                            break
                        dst.write(chunk)
                        bytes_copied += len(chunk)
                        if progress_callback:
                            progress_callback(bytes_copied, total_size)

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
        if not self.is_connected:
            raise ConnectionError("Not connected to SMB server")

        unc_path = self._get_unc_path(remote_path)

        try:
            total_size = local_path.stat().st_size

            bytes_copied = 0
            chunk_size = 1024 * 1024  # 1MB chunks

            with open(local_path, "rb") as src:
                with smbclient.open_file(unc_path, mode="wb") as dst:
                    while True:
                        chunk = src.read(chunk_size)
                        if not chunk:
                            break
                        dst.write(chunk)
                        bytes_copied += len(chunk)
                        if progress_callback:
                            progress_callback(bytes_copied, total_size)

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
        if not self.is_connected:
            return False

        unc_path = self._get_unc_path(remote_path)

        try:
            return smb_exists(unc_path)
        except Exception:
            return False

    def is_dir(self, remote_path: str) -> bool:
        """Check if a path is a directory.

        Args:
            remote_path: Path to check.

        Returns:
            True if directory.
        """
        if not self.is_connected:
            return False

        unc_path = self._get_unc_path(remote_path)

        try:
            return smb_isdir(unc_path)
        except Exception:
            return False
