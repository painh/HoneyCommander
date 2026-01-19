"""Credential management using system keychain."""

import logging

_logger = logging.getLogger(__name__)

# Try to import keyring, but make it optional
try:
    import keyring
    from keyring.errors import KeyringError

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    KeyringError = Exception  # Fallback for type hints


class CredentialManager:
    """Manages network credentials using the system keychain.

    Supports:
    - macOS: Keychain Access
    - Windows: Windows Credential Manager
    - Linux: Secret Service API (GNOME Keyring, KWallet)

    If keyring is not available, credentials will not be persisted.
    """

    SERVICE_NAME = "Commander"
    USERNAME_SUFFIX = "_username"

    @classmethod
    def is_available(cls) -> bool:
        """Check if keychain is available."""
        return KEYRING_AVAILABLE

    @classmethod
    def save_credential(cls, connection_id: str, username: str, password: str) -> bool:
        """Save credentials to the system keychain.

        Args:
            connection_id: Unique identifier for the connection.
            username: Username for the connection.
            password: Password for the connection.

        Returns:
            True if saved successfully, False otherwise.
        """
        if not KEYRING_AVAILABLE:
            _logger.warning("Keyring not available, credentials not saved")
            return False

        try:
            # Save password
            keyring.set_password(cls.SERVICE_NAME, connection_id, password)
            # Save username separately (it's not sensitive but we need it)
            keyring.set_password(
                cls.SERVICE_NAME, f"{connection_id}{cls.USERNAME_SUFFIX}", username
            )
            _logger.debug(f"Saved credentials for {connection_id}")
            return True
        except KeyringError as e:
            _logger.error(f"Failed to save credentials: {e}")
            return False

    @classmethod
    def get_credential(cls, connection_id: str) -> tuple[str | None, str | None]:
        """Get credentials from the system keychain.

        Args:
            connection_id: Unique identifier for the connection.

        Returns:
            Tuple of (username, password), or (None, None) if not found.
        """
        if not KEYRING_AVAILABLE:
            return None, None

        try:
            password = keyring.get_password(cls.SERVICE_NAME, connection_id)
            username = keyring.get_password(
                cls.SERVICE_NAME, f"{connection_id}{cls.USERNAME_SUFFIX}"
            )
            return username, password
        except KeyringError as e:
            _logger.error(f"Failed to get credentials: {e}")
            return None, None

    @classmethod
    def get_password(cls, connection_id: str) -> str | None:
        """Get only the password from the system keychain.

        Args:
            connection_id: Unique identifier for the connection.

        Returns:
            Password if found, None otherwise.
        """
        if not KEYRING_AVAILABLE:
            return None

        try:
            return keyring.get_password(cls.SERVICE_NAME, connection_id)
        except KeyringError as e:
            _logger.error(f"Failed to get password: {e}")
            return None

    @classmethod
    def delete_credential(cls, connection_id: str) -> bool:
        """Delete credentials from the system keychain.

        Args:
            connection_id: Unique identifier for the connection.

        Returns:
            True if deleted successfully, False otherwise.
        """
        if not KEYRING_AVAILABLE:
            return False

        success = True
        try:
            keyring.delete_password(cls.SERVICE_NAME, connection_id)
        except KeyringError:
            success = False

        try:
            keyring.delete_password(cls.SERVICE_NAME, f"{connection_id}{cls.USERNAME_SUFFIX}")
        except KeyringError:
            pass  # Username might not exist

        if success:
            _logger.debug(f"Deleted credentials for {connection_id}")

        return success

    @classmethod
    def has_credential(cls, connection_id: str) -> bool:
        """Check if credentials exist for a connection.

        Args:
            connection_id: Unique identifier for the connection.

        Returns:
            True if credentials exist, False otherwise.
        """
        if not KEYRING_AVAILABLE:
            return False

        try:
            password = keyring.get_password(cls.SERVICE_NAME, connection_id)
            return password is not None
        except KeyringError:
            return False
