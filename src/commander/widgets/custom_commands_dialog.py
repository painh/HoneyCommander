"""Dialog for editing custom context menu commands."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QLabel,
    QMessageBox,
    QSplitter,
    QWidget,
)
from PySide6.QtCore import Qt

from commander.utils.custom_commands import (
    CustomCommand,
    get_custom_commands_manager,
)
from commander.utils.i18n import tr


class CustomCommandsDialog(QDialog):
    """Dialog for managing custom context menu commands."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = get_custom_commands_manager()
        self._current_index = -1
        self._setup_ui()
        self._load_commands()

    def _setup_ui(self):
        """Setup the UI."""
        self.setWindowTitle(tr("custom_commands_title"))
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left side - command list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._list)

        # List buttons
        list_btn_layout = QHBoxLayout()
        self._add_btn = QPushButton(tr("add"))
        self._add_btn.clicked.connect(self._add_command)
        list_btn_layout.addWidget(self._add_btn)

        self._remove_btn = QPushButton(tr("delete"))
        self._remove_btn.clicked.connect(self._remove_command)
        list_btn_layout.addWidget(self._remove_btn)

        self._up_btn = QPushButton("▲")
        self._up_btn.setFixedWidth(30)
        self._up_btn.clicked.connect(self._move_up)
        list_btn_layout.addWidget(self._up_btn)

        self._down_btn = QPushButton("▼")
        self._down_btn.setFixedWidth(30)
        self._down_btn.clicked.connect(self._move_down)
        list_btn_layout.addWidget(self._down_btn)

        left_layout.addLayout(list_btn_layout)
        splitter.addWidget(left_widget)

        # Right side - command editor
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Editor group
        editor_group = QGroupBox(tr("custom_commands_edit"))
        editor_form = QFormLayout(editor_group)

        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._on_field_changed)
        editor_form.addRow(tr("custom_commands_name"), self._name_edit)

        self._command_edit = QLineEdit()
        self._command_edit.textChanged.connect(self._on_field_changed)
        editor_form.addRow(tr("custom_commands_command"), self._command_edit)

        # Help text for placeholders
        help_label = QLabel(tr("custom_commands_placeholders"))
        help_label.setStyleSheet("color: #888; font-size: 11px;")
        help_label.setWordWrap(True)
        editor_form.addRow("", help_label)

        self._extensions_edit = QLineEdit()
        self._extensions_edit.setPlaceholderText(tr("custom_commands_extensions_placeholder"))
        self._extensions_edit.textChanged.connect(self._on_field_changed)
        editor_form.addRow(tr("custom_commands_extensions"), self._extensions_edit)

        self._for_files_cb = QCheckBox(tr("custom_commands_for_files"))
        self._for_files_cb.stateChanged.connect(self._on_field_changed)
        editor_form.addRow("", self._for_files_cb)

        self._for_dirs_cb = QCheckBox(tr("custom_commands_for_dirs"))
        self._for_dirs_cb.stateChanged.connect(self._on_field_changed)
        editor_form.addRow("", self._for_dirs_cb)

        self._enabled_cb = QCheckBox(tr("custom_commands_enabled"))
        self._enabled_cb.stateChanged.connect(self._on_field_changed)
        editor_form.addRow("", self._enabled_cb)

        right_layout.addWidget(editor_group)
        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setSizes([250, 450])

        # Bottom buttons
        bottom_layout = QHBoxLayout()

        reset_btn = QPushButton(tr("custom_commands_reset"))
        reset_btn.clicked.connect(self._reset_to_defaults)
        bottom_layout.addWidget(reset_btn)

        bottom_layout.addStretch()

        close_btn = QPushButton(tr("ok"))
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)

        layout.addLayout(bottom_layout)

    def _load_commands(self):
        """Load commands into list."""
        self._list.clear()
        for cmd in self._manager.get_commands():
            item = QListWidgetItem(cmd.name)
            if not cmd.enabled:
                item.setForeground(Qt.GlobalColor.gray)
            self._list.addItem(item)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)

        self._update_buttons()

    def _on_selection_changed(self, row: int):
        """Handle list selection change."""
        # Save current before switching
        if self._current_index >= 0:
            self._save_current()

        self._current_index = row

        if row >= 0:
            commands = self._manager.get_commands()
            if row < len(commands):
                cmd = commands[row]
                self._load_command_to_editor(cmd)
        else:
            self._clear_editor()

        self._update_buttons()

    def _load_command_to_editor(self, cmd: CustomCommand):
        """Load command into editor fields."""
        # Block signals while loading
        self._name_edit.blockSignals(True)
        self._command_edit.blockSignals(True)
        self._extensions_edit.blockSignals(True)
        self._for_files_cb.blockSignals(True)
        self._for_dirs_cb.blockSignals(True)
        self._enabled_cb.blockSignals(True)

        self._name_edit.setText(cmd.name)
        self._command_edit.setText(cmd.command)
        self._extensions_edit.setText(", ".join(cmd.extensions))
        self._for_files_cb.setChecked(cmd.for_files)
        self._for_dirs_cb.setChecked(cmd.for_directories)
        self._enabled_cb.setChecked(cmd.enabled)

        # Check if it's a built-in command (non-editable command field)
        is_builtin = self._manager.is_builtin_command(cmd)
        self._command_edit.setReadOnly(is_builtin)
        if is_builtin:
            self._command_edit.setStyleSheet("background-color: #f0f0f0;")
        else:
            self._command_edit.setStyleSheet("")

        self._name_edit.blockSignals(False)
        self._command_edit.blockSignals(False)
        self._extensions_edit.blockSignals(False)
        self._for_files_cb.blockSignals(False)
        self._for_dirs_cb.blockSignals(False)
        self._enabled_cb.blockSignals(False)

    def _clear_editor(self):
        """Clear editor fields."""
        self._name_edit.clear()
        self._command_edit.clear()
        self._extensions_edit.clear()
        self._for_files_cb.setChecked(True)
        self._for_dirs_cb.setChecked(True)
        self._enabled_cb.setChecked(True)

    def _on_field_changed(self):
        """Handle field change - save immediately."""
        if self._current_index >= 0:
            self._save_current()
            # Update list item text
            item = self._list.item(self._current_index)
            if item:
                item.setText(self._name_edit.text())
                if self._enabled_cb.isChecked():
                    item.setForeground(Qt.GlobalColor.black)
                else:
                    item.setForeground(Qt.GlobalColor.gray)

    def _save_current(self):
        """Save current editor state to command."""
        if self._current_index < 0:
            return

        extensions = [
            e.strip().lstrip(".") for e in self._extensions_edit.text().split(",") if e.strip()
        ]

        cmd = CustomCommand(
            name=self._name_edit.text(),
            command=self._command_edit.text(),
            extensions=extensions,
            for_files=self._for_files_cb.isChecked(),
            for_directories=self._for_dirs_cb.isChecked(),
            enabled=self._enabled_cb.isChecked(),
        )

        self._manager.update_command(self._current_index, cmd)

    def _add_command(self):
        """Add a new command."""
        cmd = CustomCommand(
            name=tr("custom_commands_new"),
            command="",
            extensions=[],
            for_files=True,
            for_directories=True,
            enabled=True,
        )
        self._manager.add_command(cmd)
        self._load_commands()
        self._list.setCurrentRow(self._list.count() - 1)

    def _remove_command(self):
        """Remove selected command."""
        if self._current_index < 0:
            return

        reply = QMessageBox.question(
            self,
            tr("delete"),
            tr("custom_commands_confirm_delete"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._manager.remove_command(self._current_index)
            self._current_index = -1
            self._load_commands()

    def _move_up(self):
        """Move selected command up."""
        if self._current_index > 0:
            self._manager.move_command(self._current_index, self._current_index - 1)
            new_index = self._current_index - 1
            self._current_index = -1  # Prevent save during reload
            self._load_commands()
            self._list.setCurrentRow(new_index)

    def _move_down(self):
        """Move selected command down."""
        if self._current_index < self._list.count() - 1:
            self._manager.move_command(self._current_index, self._current_index + 1)
            new_index = self._current_index + 1
            self._current_index = -1  # Prevent save during reload
            self._load_commands()
            self._list.setCurrentRow(new_index)

    def _reset_to_defaults(self):
        """Reset all commands to defaults."""
        reply = QMessageBox.question(
            self,
            tr("custom_commands_reset"),
            tr("custom_commands_confirm_reset"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._manager.reset_to_defaults()
            self._current_index = -1
            self._load_commands()

    def _update_buttons(self):
        """Update button enabled states."""
        has_selection = self._current_index >= 0
        self._remove_btn.setEnabled(has_selection)
        self._up_btn.setEnabled(self._current_index > 0)
        self._down_btn.setEnabled(has_selection and self._current_index < self._list.count() - 1)
