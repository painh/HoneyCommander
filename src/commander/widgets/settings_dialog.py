"""Settings dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QGroupBox,
    QFormLayout,
)

from commander.utils.settings import Settings
from commander.utils.i18n import get_i18n, tr, I18n


class SettingsDialog(QDialog):
    """Settings dialog for configuring application preferences."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = Settings()
        self._i18n = get_i18n()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Setup UI."""
        self.setWindowTitle(tr("settings") if "settings" in I18n.LANGUAGE_NAMES else "Settings")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Language group
        lang_group = QGroupBox("Language / 언어")
        lang_layout = QFormLayout(lang_group)

        self._lang_combo = QComboBox()
        # Add "System Default" option
        self._lang_combo.addItem("System Default", "auto")
        for code in I18n.SUPPORTED_LANGUAGES:
            name = I18n.LANGUAGE_NAMES.get(code, code)
            self._lang_combo.addItem(name, code)

        lang_layout.addRow("Language:", self._lang_combo)

        # Note about restart
        note_label = QLabel("* Restart required to apply language changes\n* 언어 변경 시 재시작 필요")
        note_label.setStyleSheet("color: #888; font-size: 11px;")
        lang_layout.addRow(note_label)

        layout.addWidget(lang_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton(tr("cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton(tr("ok"))
        ok_btn.clicked.connect(self._save_and_accept)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    def _load_settings(self):
        """Load current settings."""
        saved_lang = self._settings.load_language()
        if saved_lang:
            index = self._lang_combo.findData(saved_lang)
            if index >= 0:
                self._lang_combo.setCurrentIndex(index)
        else:
            # System default
            self._lang_combo.setCurrentIndex(0)

    def _save_and_accept(self):
        """Save settings and close."""
        # Language
        lang_code = self._lang_combo.currentData()
        if lang_code == "auto":
            # Clear saved language to use system default
            self._settings._settings.remove("general/language")
        else:
            self._settings.save_language(lang_code)

        self.accept()
