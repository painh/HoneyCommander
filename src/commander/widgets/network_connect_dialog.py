"""Network connection dialog for adding/editing network drives."""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from commander.core.network import ConnectionConfig, CredentialManager

_logger = logging.getLogger(__name__)


class NetworkConnectDialog(QDialog):
    """Dialog for configuring network connections."""

    def __init__(
        self,
        parent=None,
        config: ConnectionConfig | None = None,
        connection_id: str | None = None,
    ):
        """Initialize the dialog.

        Args:
            parent: Parent widget.
            config: Existing configuration to edit (None for new connection).
            connection_id: ID of existing connection (for editing).
        """
        super().__init__(parent)
        self._config = config
        self._connection_id = connection_id
        self._editing = config is not None

        self._setup_ui()

        if config:
            self._load_config(config)

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle(
            "Edit Network Connection" if self._editing else "Add Network Connection"
        )
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Protocol selection
        protocol_layout = QHBoxLayout()
        protocol_layout.addWidget(QLabel("Protocol:"))
        self._protocol_combo = QComboBox()
        self._protocol_combo.addItem("SMB/CIFS (Windows Share)", "smb")
        self._protocol_combo.addItem("SFTP (SSH File Transfer)", "sftp")
        self._protocol_combo.currentIndexChanged.connect(self._on_protocol_changed)
        protocol_layout.addWidget(self._protocol_combo, 1)
        layout.addLayout(protocol_layout)

        # Stacked widget for protocol-specific settings
        self._stack = QStackedWidget()

        # SMB settings
        self._smb_widget = self._create_smb_widget()
        self._stack.addWidget(self._smb_widget)

        # SFTP settings
        self._sftp_widget = self._create_sftp_widget()
        self._stack.addWidget(self._sftp_widget)

        layout.addWidget(self._stack)

        # Common settings
        common_group = QGroupBox("Connection Settings")
        common_layout = QFormLayout(common_group)

        self._display_name = QLineEdit()
        self._display_name.setPlaceholderText("Optional display name")
        common_layout.addRow("Display Name:", self._display_name)

        self._save_password = QCheckBox("Save password in system keychain")
        self._save_password.setChecked(True)
        common_layout.addRow("", self._save_password)

        layout.addWidget(common_group)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_smb_widget(self) -> QWidget:
        """Create SMB settings widget."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Host
        self._smb_host = QLineEdit()
        self._smb_host.setPlaceholderText("server.local or 192.168.1.100")
        layout.addRow("Host:", self._smb_host)

        # Share
        self._smb_share = QLineEdit()
        self._smb_share.setPlaceholderText("shared_folder")
        layout.addRow("Share:", self._smb_share)

        # Port
        port_layout = QHBoxLayout()
        self._smb_port = QSpinBox()
        self._smb_port.setRange(1, 65535)
        self._smb_port.setValue(445)
        self._smb_port.setSpecialValueText("Default (445)")
        port_layout.addWidget(self._smb_port)
        port_layout.addStretch()
        layout.addRow("Port:", port_layout)

        # Domain
        self._smb_domain = QLineEdit()
        self._smb_domain.setPlaceholderText("Optional (WORKGROUP)")
        layout.addRow("Domain:", self._smb_domain)

        # Username
        self._smb_username = QLineEdit()
        self._smb_username.setPlaceholderText("username")
        layout.addRow("Username:", self._smb_username)

        # Password
        self._smb_password = QLineEdit()
        self._smb_password.setEchoMode(QLineEdit.Password)
        self._smb_password.setPlaceholderText("password")
        layout.addRow("Password:", self._smb_password)

        return widget

    def _create_sftp_widget(self) -> QWidget:
        """Create SFTP settings widget."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Host
        self._sftp_host = QLineEdit()
        self._sftp_host.setPlaceholderText("server.example.com")
        layout.addRow("Host:", self._sftp_host)

        # Port
        port_layout = QHBoxLayout()
        self._sftp_port = QSpinBox()
        self._sftp_port.setRange(1, 65535)
        self._sftp_port.setValue(22)
        port_layout.addWidget(self._sftp_port)
        port_layout.addStretch()
        layout.addRow("Port:", port_layout)

        # Username
        self._sftp_username = QLineEdit()
        self._sftp_username.setPlaceholderText("username")
        layout.addRow("Username:", self._sftp_username)

        # Authentication method
        self._sftp_auth_combo = QComboBox()
        self._sftp_auth_combo.addItem("Password", "password")
        self._sftp_auth_combo.addItem("SSH Key", "key")
        self._sftp_auth_combo.currentIndexChanged.connect(self._on_sftp_auth_changed)
        layout.addRow("Authentication:", self._sftp_auth_combo)

        # Password (for password auth)
        self._sftp_password = QLineEdit()
        self._sftp_password.setEchoMode(QLineEdit.Password)
        self._sftp_password.setPlaceholderText("password")
        layout.addRow("Password:", self._sftp_password)

        # Key file (for key auth)
        key_layout = QHBoxLayout()
        self._sftp_key_file = QLineEdit()
        self._sftp_key_file.setPlaceholderText("~/.ssh/id_rsa")
        key_layout.addWidget(self._sftp_key_file)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_key_file)
        key_layout.addWidget(browse_btn)
        self._sftp_key_row_widget = QWidget()
        self._sftp_key_row_widget.setLayout(key_layout)
        layout.addRow("Key File:", self._sftp_key_row_widget)

        # Key passphrase
        self._sftp_key_passphrase = QLineEdit()
        self._sftp_key_passphrase.setEchoMode(QLineEdit.Password)
        self._sftp_key_passphrase.setPlaceholderText("Optional passphrase")
        self._sftp_passphrase_label = QLabel("Passphrase:")
        layout.addRow(self._sftp_passphrase_label, self._sftp_key_passphrase)

        # Set initial visibility
        self._on_sftp_auth_changed()

        return widget

    def _on_protocol_changed(self) -> None:
        """Handle protocol selection change."""
        protocol = self._protocol_combo.currentData()
        if protocol == "smb":
            self._stack.setCurrentWidget(self._smb_widget)
        else:
            self._stack.setCurrentWidget(self._sftp_widget)

    def _on_sftp_auth_changed(self) -> None:
        """Handle SFTP auth method change."""
        auth = self._sftp_auth_combo.currentData()
        is_password = auth == "password"

        self._sftp_password.setVisible(is_password)
        # Find the password label in the form layout
        sftp_layout = self._sftp_widget.layout()
        for i in range(sftp_layout.rowCount()):
            label = sftp_layout.itemAt(i, QFormLayout.LabelRole)
            field = sftp_layout.itemAt(i, QFormLayout.FieldRole)
            if field and field.widget() == self._sftp_password:
                if label:
                    label.widget().setVisible(is_password)

        self._sftp_key_row_widget.setVisible(not is_password)
        self._sftp_key_passphrase.setVisible(not is_password)
        self._sftp_passphrase_label.setVisible(not is_password)

    def _browse_key_file(self) -> None:
        """Browse for SSH key file."""
        ssh_dir = Path.home() / ".ssh"
        start_dir = str(ssh_dir) if ssh_dir.exists() else str(Path.home())

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SSH Key File",
            start_dir,
            "All Files (*)",
        )

        if file_path:
            self._sftp_key_file.setText(file_path)

    def _load_config(self, config: ConnectionConfig) -> None:
        """Load configuration into the dialog."""
        # Set protocol
        protocol = config.protocol.lower()
        index = self._protocol_combo.findData(protocol)
        if index >= 0:
            self._protocol_combo.setCurrentIndex(index)

        # Set display name
        if config.display_name:
            self._display_name.setText(config.display_name)

        if protocol == "smb":
            self._smb_host.setText(config.host)
            self._smb_share.setText(config.share or "")
            if config.port:
                self._smb_port.setValue(config.port)
            if config.domain:
                self._smb_domain.setText(config.domain)
            if config.username:
                self._smb_username.setText(config.username)

            # Try to load password from keychain
            if self._connection_id:
                password = CredentialManager.get_password(self._connection_id)
                if password:
                    self._smb_password.setText(password)

        elif protocol == "sftp":
            self._sftp_host.setText(config.host)
            if config.port:
                self._sftp_port.setValue(config.port)
            if config.username:
                self._sftp_username.setText(config.username)

            if config.key_file:
                self._sftp_auth_combo.setCurrentIndex(1)  # SSH Key
                self._sftp_key_file.setText(config.key_file)
            else:
                self._sftp_auth_combo.setCurrentIndex(0)  # Password

            # Try to load password/passphrase from keychain
            if self._connection_id:
                password = CredentialManager.get_password(self._connection_id)
                if password:
                    if config.key_file:
                        self._sftp_key_passphrase.setText(password)
                    else:
                        self._sftp_password.setText(password)

    def _validate(self) -> bool:
        """Validate input.

        Returns:
            True if valid, False otherwise.
        """
        protocol = self._protocol_combo.currentData()

        if protocol == "smb":
            if not self._smb_host.text().strip():
                QMessageBox.warning(self, "Validation Error", "Host is required")
                self._smb_host.setFocus()
                return False
            if not self._smb_share.text().strip():
                QMessageBox.warning(self, "Validation Error", "Share name is required")
                self._smb_share.setFocus()
                return False

        elif protocol == "sftp":
            if not self._sftp_host.text().strip():
                QMessageBox.warning(self, "Validation Error", "Host is required")
                self._sftp_host.setFocus()
                return False

            auth = self._sftp_auth_combo.currentData()
            if auth == "key":
                key_file = self._sftp_key_file.text().strip()
                if key_file:
                    key_path = Path(key_file).expanduser()
                    if not key_path.exists():
                        QMessageBox.warning(
                            self, "Validation Error", f"Key file not found: {key_file}"
                        )
                        self._sftp_key_file.setFocus()
                        return False

        return True

    def _on_accept(self) -> None:
        """Handle accept button."""
        if self._validate():
            self.accept()

    def get_config(self) -> ConnectionConfig:
        """Get the connection configuration.

        Returns:
            ConnectionConfig with the entered values.
        """
        protocol = self._protocol_combo.currentData()
        display_name = self._display_name.text().strip() or None

        if protocol == "smb":
            port = self._smb_port.value()
            if port == 445:
                port = None  # Use default

            return ConnectionConfig(
                protocol="smb",
                host=self._smb_host.text().strip(),
                port=port,
                share=self._smb_share.text().strip(),
                username=self._smb_username.text().strip() or None,
                display_name=display_name,
                domain=self._smb_domain.text().strip() or None,
                connection_id=self._connection_id,
            )

        else:  # sftp
            port = self._sftp_port.value()
            if port == 22:
                port = None  # Use default

            auth = self._sftp_auth_combo.currentData()
            key_file = None
            if auth == "key":
                key_file = self._sftp_key_file.text().strip() or None

            return ConnectionConfig(
                protocol="sftp",
                host=self._sftp_host.text().strip(),
                port=port,
                username=self._sftp_username.text().strip() or None,
                display_name=display_name,
                key_file=key_file,
                connection_id=self._connection_id,
            )

    def get_password(self) -> str | None:
        """Get the entered password.

        Returns:
            Password string, or None if not entered.
        """
        protocol = self._protocol_combo.currentData()

        if protocol == "smb":
            return self._smb_password.text() or None
        else:
            auth = self._sftp_auth_combo.currentData()
            if auth == "key":
                return self._sftp_key_passphrase.text() or None
            else:
                return self._sftp_password.text() or None

    def should_save_password(self) -> bool:
        """Check if password should be saved.

        Returns:
            True if password should be saved.
        """
        return self._save_password.isChecked()
