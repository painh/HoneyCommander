"""Settings dialog."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QSpinBox,
    QTabWidget,
    QWidget,
    QCheckBox,
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
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # === General Tab ===
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        # Language group
        lang_group = QGroupBox("Language / 언어")
        lang_layout = QFormLayout(lang_group)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem("System Default", "auto")
        for code in I18n.SUPPORTED_LANGUAGES:
            name = I18n.LANGUAGE_NAMES.get(code, code)
            self._lang_combo.addItem(name, code)

        lang_layout.addRow("Language:", self._lang_combo)

        note_label = QLabel("* Restart required / 재시작 필요")
        note_label.setStyleSheet("color: #888; font-size: 11px;")
        lang_layout.addRow(note_label)

        general_layout.addWidget(lang_group)
        general_layout.addStretch()
        tabs.addTab(general_tab, tr("settings_general"))

        # === View Tab ===
        view_tab = QWidget()
        view_layout = QVBoxLayout(view_tab)

        view_group = QGroupBox(tr("settings_thumbnails"))
        view_form = QFormLayout(view_group)

        self._thumb_size_spin = QSpinBox()
        self._thumb_size_spin.setRange(64, 256)
        self._thumb_size_spin.setSuffix(" px")
        view_form.addRow(tr("settings_thumbnail_size"), self._thumb_size_spin)

        self._anim_thumb_spin = QSpinBox()
        self._anim_thumb_spin.setRange(40, 120)
        self._anim_thumb_spin.setSuffix(" px")
        view_form.addRow(tr("settings_anim_thumb_size"), self._anim_thumb_spin)

        view_layout.addWidget(view_group)
        view_layout.addStretch()
        tabs.addTab(view_tab, tr("settings_view"))

        # === Search Tab ===
        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)

        search_group = QGroupBox(tr("settings_search"))
        search_form = QFormLayout(search_group)

        self._fuzzy_timeout_spin = QSpinBox()
        self._fuzzy_timeout_spin.setRange(500, 5000)
        self._fuzzy_timeout_spin.setSingleStep(100)
        self._fuzzy_timeout_spin.setSuffix(" ms")
        search_form.addRow(tr("settings_fuzzy_timeout"), self._fuzzy_timeout_spin)

        self._max_results_spin = QSpinBox()
        self._max_results_spin.setRange(50, 1000)
        self._max_results_spin.setSingleStep(50)
        search_form.addRow(tr("settings_max_results"), self._max_results_spin)

        search_layout.addWidget(search_group)
        search_layout.addStretch()
        tabs.addTab(search_tab, tr("settings_search"))

        # === Performance Tab ===
        perf_tab = QWidget()
        perf_layout = QVBoxLayout(perf_tab)

        perf_group = QGroupBox(tr("settings_performance"))
        perf_form = QFormLayout(perf_group)

        self._cache_size_spin = QSpinBox()
        self._cache_size_spin.setRange(100, 2000)
        self._cache_size_spin.setSingleStep(100)
        perf_form.addRow(tr("settings_cache_size"), self._cache_size_spin)

        self._undo_stack_spin = QSpinBox()
        self._undo_stack_spin.setRange(10, 200)
        self._undo_stack_spin.setSingleStep(10)
        perf_form.addRow(tr("settings_undo_stack"), self._undo_stack_spin)

        perf_layout.addWidget(perf_group)

        # Debug group
        debug_group = QGroupBox(tr("settings_debug"))
        debug_form = QFormLayout(debug_group)

        self._logging_checkbox = QCheckBox()
        debug_form.addRow(tr("settings_logging_enabled"), self._logging_checkbox)

        from commander.utils.logger import get_log_path

        log_path_label = QLabel(str(get_log_path()))
        log_path_label.setStyleSheet("color: #888; font-size: 11px;")
        log_path_label.setWordWrap(True)
        debug_form.addRow(tr("settings_log_path"), log_path_label)

        perf_layout.addWidget(debug_group)
        perf_layout.addStretch()
        tabs.addTab(perf_tab, tr("settings_performance"))

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
        # Language
        saved_lang = self._settings.load_language()
        if saved_lang:
            index = self._lang_combo.findData(saved_lang)
            if index >= 0:
                self._lang_combo.setCurrentIndex(index)
        else:
            self._lang_combo.setCurrentIndex(0)

        # View
        self._thumb_size_spin.setValue(self._settings.load_thumbnail_size())
        self._anim_thumb_spin.setValue(self._settings.load_animation_thumb_size())

        # Search
        self._fuzzy_timeout_spin.setValue(self._settings.load_fuzzy_search_timeout())
        self._max_results_spin.setValue(self._settings.load_search_max_results())

        # Performance
        self._cache_size_spin.setValue(self._settings.load_thumbnail_cache_size())
        self._undo_stack_spin.setValue(self._settings.load_undo_stack_size())

        # Debug
        self._logging_checkbox.setChecked(self._settings.load_logging_enabled())

    def _save_and_accept(self):
        """Save settings and close."""
        # Language
        lang_code = self._lang_combo.currentData()
        if lang_code == "auto":
            self._settings._settings.remove("general/language")
        else:
            self._settings.save_language(lang_code)

        # View
        self._settings.save_thumbnail_size(self._thumb_size_spin.value())
        self._settings.save_animation_thumb_size(self._anim_thumb_spin.value())

        # Search
        self._settings.save_fuzzy_search_timeout(self._fuzzy_timeout_spin.value())
        self._settings.save_search_max_results(self._max_results_spin.value())

        # Performance
        self._settings.save_thumbnail_cache_size(self._cache_size_spin.value())
        self._settings.save_undo_stack_size(self._undo_stack_spin.value())

        # Debug - use logger module to properly toggle file logging
        from commander.utils.logger import set_logging_enabled

        set_logging_enabled(self._logging_checkbox.isChecked())

        self.accept()
