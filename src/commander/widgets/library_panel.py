"""Library panel with tab-based switching for Asset Manager."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabBar,
    QPushButton,
    QMenu,
    QLabel,
    QSizePolicy,
)

from ..core.asset_manager import Library, get_library_manager
from .library_dialog import (
    LibraryCreateDialog,
    LibraryManagerDialog,
    LibraryScanDialog,
)


class LibraryTabBar(QTabBar):
    """Custom tab bar for library switching."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(False)
        self.setTabsClosable(False)
        self.setMovable(False)
        self.setDrawBase(False)


class LibraryPanel(QWidget):
    """Panel for switching between file explorer and asset libraries.

    Signals:
        mode_changed: Emitted when mode changes ("explorer" or "library")
        library_selected: Emitted when a library is selected (library_id)
        tag_filter_changed: Emitted when tag filter changes (list of tag_ids)
    """

    mode_changed = Signal(str)
    library_selected = Signal(int)
    tag_filter_changed = Signal(list)

    # Explorer mode constant
    EXPLORER_MODE = "explorer"
    LIBRARY_MODE = "library"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_library_id: Optional[int] = None
        self._current_mode = self.EXPLORER_MODE
        self._current_folder_path: Optional[Path] = None
        self._setup_ui()
        self._load_libraries()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab bar container
        tab_container = QWidget()
        tab_container.setObjectName("libraryTabContainer")
        tab_layout = QHBoxLayout(tab_container)
        tab_layout.setContentsMargins(4, 4, 4, 4)
        tab_layout.setSpacing(2)

        # Tab bar
        self._tab_bar = LibraryTabBar()
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        tab_layout.addWidget(self._tab_bar, 1)

        # Add button
        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(24, 24)
        self._add_btn.setToolTip("Add or manage libraries")
        self._add_btn.clicked.connect(self._show_add_menu)
        tab_layout.addWidget(self._add_btn)

        layout.addWidget(tab_container)

        # Tag filter area (will be populated by tag_filter.py)
        self._tag_filter_container = QWidget()
        self._tag_filter_layout = QVBoxLayout(self._tag_filter_container)
        self._tag_filter_layout.setContentsMargins(4, 4, 4, 4)
        self._tag_filter_container.hide()  # Hidden in explorer mode
        layout.addWidget(self._tag_filter_container)

        # Info label for library mode
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet("color: gray; padding: 8px;")
        self._info_label.hide()
        layout.addWidget(self._info_label)

        # Stretch to fill remaining space
        layout.addStretch()

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

    def _load_libraries(self) -> None:
        """Load libraries into tabs."""
        # Remember current selection
        current_index = self._tab_bar.currentIndex()

        # Block signals during reload
        self._tab_bar.blockSignals(True)

        # Clear existing tabs
        while self._tab_bar.count() > 0:
            self._tab_bar.removeTab(0)

        # Add explorer tab
        self._tab_bar.addTab("Explorer")
        self._tab_bar.setTabData(0, None)  # None = explorer mode

        # Add library tabs
        lib_manager = get_library_manager()
        libraries = lib_manager.get_all_libraries()

        for lib in libraries:
            index = self._tab_bar.addTab(lib.name)
            self._tab_bar.setTabData(index, lib.id)
            self._tab_bar.setTabToolTip(index, str(lib.root_path))

        self._tab_bar.blockSignals(False)

        # Restore selection
        if current_index >= 0 and current_index < self._tab_bar.count():
            self._tab_bar.setCurrentIndex(current_index)
        else:
            self._tab_bar.setCurrentIndex(0)

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change."""
        if index < 0:
            return

        library_id = self._tab_bar.tabData(index)

        if library_id is None:
            # Explorer mode
            self._current_mode = self.EXPLORER_MODE
            self._current_library_id = None
            self._tag_filter_container.hide()
            self._info_label.hide()
            self.mode_changed.emit(self.EXPLORER_MODE)
        else:
            # Library mode
            self._current_mode = self.LIBRARY_MODE
            self._current_library_id = library_id
            self._tag_filter_container.show()
            self._update_info_label()
            self.mode_changed.emit(self.LIBRARY_MODE)
            self.library_selected.emit(library_id)

    def _update_info_label(self) -> None:
        """Update info label with library stats."""
        if self._current_library_id is None:
            self._info_label.hide()
            return

        lib_manager = get_library_manager()
        stats = lib_manager.get_library_stats(self._current_library_id)

        if stats["total_assets"] == 0:
            self._info_label.setText("No assets found.\nClick 'Scan Library' to index files.")
            self._info_label.show()
        else:
            self._info_label.hide()

    def _show_add_menu(self) -> None:
        """Show add/manage menu."""
        menu = QMenu(self)

        add_action = menu.addAction("Add Library...")
        add_action.triggered.connect(self._add_library)

        menu.addSeparator()

        manage_action = menu.addAction("Manage Libraries...")
        manage_action.triggered.connect(self._manage_libraries)

        if self._current_library_id is not None:
            menu.addSeparator()
            scan_action = menu.addAction("Scan Current Library")
            scan_action.triggered.connect(self._scan_current_library)

        menu.exec(self._add_btn.mapToGlobal(self._add_btn.rect().bottomLeft()))

    def _add_library(self) -> None:
        """Add a new library."""
        dialog = LibraryCreateDialog(self._current_folder_path, self)
        dialog.library_created.connect(self._on_library_created)
        dialog.exec()

    def _on_library_created(self, library_id: int) -> None:
        """Handle new library created."""
        self._load_libraries()

        # Switch to new library
        for i in range(self._tab_bar.count()):
            if self._tab_bar.tabData(i) == library_id:
                self._tab_bar.setCurrentIndex(i)
                break

        # Prompt to scan
        lib_manager = get_library_manager()
        library = lib_manager.get_library(library_id)
        if library:
            dialog = LibraryScanDialog(library, incremental=True, parent=self)
            dialog.exec()
            self._update_info_label()

    def _manage_libraries(self) -> None:
        """Open library manager dialog."""
        dialog = LibraryManagerDialog(self)
        dialog.library_selected.connect(self._select_library)
        dialog.exec()
        self._load_libraries()

    def _select_library(self, library_id: int) -> None:
        """Select a library by ID."""
        for i in range(self._tab_bar.count()):
            if self._tab_bar.tabData(i) == library_id:
                self._tab_bar.setCurrentIndex(i)
                break

    def _scan_current_library(self) -> None:
        """Scan the current library."""
        if self._current_library_id is None:
            return

        lib_manager = get_library_manager()
        library = lib_manager.get_library(self._current_library_id)
        if library:
            dialog = LibraryScanDialog(library, incremental=True, parent=self)
            dialog.exec()
            self._update_info_label()

    # === Public API ===

    @property
    def current_mode(self) -> str:
        """Get current mode ('explorer' or 'library')."""
        return self._current_mode

    @property
    def current_library_id(self) -> Optional[int]:
        """Get current library ID (None if in explorer mode)."""
        return self._current_library_id

    def get_current_library(self) -> Optional[Library]:
        """Get current library object."""
        if self._current_library_id is None:
            return None
        return get_library_manager().get_library(self._current_library_id)

    def set_tag_filter_widget(self, widget: QWidget) -> None:
        """Set the tag filter widget."""
        # Clear existing
        while self._tag_filter_layout.count() > 0:
            item = self._tag_filter_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new widget
        self._tag_filter_layout.addWidget(widget)

    def refresh(self) -> None:
        """Refresh library list."""
        self._load_libraries()
        self._update_info_label()

    def switch_to_explorer(self) -> None:
        """Switch to explorer mode."""
        self._tab_bar.setCurrentIndex(0)

    def switch_to_library(self, library_id: int) -> None:
        """Switch to a specific library."""
        self._select_library(library_id)

    def set_current_folder(self, path: Optional[Path]) -> None:
        """Set current folder path for library creation default."""
        self._current_folder_path = path
