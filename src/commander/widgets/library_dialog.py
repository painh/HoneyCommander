"""Library management dialogs for Asset Manager."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QFileDialog,
    QLabel,
    QProgressBar,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QGroupBox,
)

from ..core.asset_manager import (
    Library,
    LibraryScanner,
    get_library_manager,
)


class LibraryCreateDialog(QDialog):
    """Dialog for creating a new asset library."""

    library_created = Signal(int)  # library_id

    def __init__(self, initial_path: Optional[Path] = None, parent=None):
        super().__init__(parent)
        self._initial_path = initial_path
        self.setWindowTitle("Create Asset Library")
        self.setMinimumWidth(450)
        self._setup_ui()
        self._apply_initial_path()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Form
        form = QFormLayout()

        # Name input
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("My Assets")
        form.addRow("Name:", self._name_edit)

        # Path input with browse button
        path_layout = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("/path/to/assets")
        self._path_edit.setReadOnly(True)
        path_layout.addWidget(self._path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        path_layout.addWidget(browse_btn)

        form.addRow("Path:", path_layout)

        # Options
        self._scan_subdirs = QCheckBox("Scan subdirectories")
        self._scan_subdirs.setChecked(True)
        form.addRow("", self._scan_subdirs)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._create_btn = QPushButton("Create")
        self._create_btn.setDefault(True)
        self._create_btn.clicked.connect(self._create_library)
        self._create_btn.setEnabled(False)
        btn_layout.addWidget(self._create_btn)

        layout.addLayout(btn_layout)

        # Validate on input
        self._name_edit.textChanged.connect(self._validate)
        self._path_edit.textChanged.connect(self._validate)

    def _apply_initial_path(self) -> None:
        """Apply initial path if provided."""
        if self._initial_path and self._initial_path.exists():
            self._path_edit.setText(str(self._initial_path))
            self._name_edit.setText(self._initial_path.name)
            self._validate()

    def _browse_folder(self) -> None:
        """Open folder browser dialog."""
        # Use current path or initial path as starting point
        start_path = self._path_edit.text() or (
            str(self._initial_path) if self._initial_path else str(Path.home())
        )
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Asset Folder",
            start_path,
        )
        if folder:
            self._path_edit.setText(folder)
            # Auto-fill name if empty
            if not self._name_edit.text():
                self._name_edit.setText(Path(folder).name)

    def _validate(self) -> None:
        """Validate inputs."""
        name = self._name_edit.text().strip()
        path = self._path_edit.text().strip()

        valid = bool(name) and bool(path) and Path(path).exists()
        self._create_btn.setEnabled(valid)

    def _create_library(self) -> None:
        """Create the library."""
        name = self._name_edit.text().strip()
        path = Path(self._path_edit.text().strip())
        scan_subdirs = self._scan_subdirs.isChecked()

        try:
            lib_manager = get_library_manager()
            library = lib_manager.create_library(name, path, scan_subdirs)
            self.library_created.emit(library.id)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create library: {e}")


class LibraryEditDialog(QDialog):
    """Dialog for editing library properties."""

    library_updated = Signal(int)  # library_id

    def __init__(self, library: Library, parent=None):
        super().__init__(parent)
        self._library = library
        self.setWindowTitle(f"Edit Library: {library.name}")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Form
        form = QFormLayout()

        # Name
        self._name_edit = QLineEdit(self._library.name)
        form.addRow("Name:", self._name_edit)

        # Path (read-only)
        path_label = QLabel(str(self._library.root_path))
        path_label.setWordWrap(True)
        form.addRow("Path:", path_label)

        # Options
        self._scan_subdirs = QCheckBox("Scan subdirectories")
        self._scan_subdirs.setChecked(self._library.scan_subdirs)
        form.addRow("", self._scan_subdirs)

        layout.addLayout(form)

        # Stats
        stats_group = QGroupBox("Statistics")
        stats_layout = QFormLayout(stats_group)

        lib_manager = get_library_manager()
        stats = lib_manager.get_library_stats(self._library.id)

        stats_layout.addRow("Total assets:", QLabel(str(stats["total_assets"])))
        stats_layout.addRow("Tagged assets:", QLabel(str(stats["tagged_assets"])))
        stats_layout.addRow("Missing files:", QLabel(str(stats["missing_assets"])))

        layout.addWidget(stats_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _save(self) -> None:
        """Save changes."""
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Name is required")
            return

        try:
            self._library.name = name
            self._library.scan_subdirs = self._scan_subdirs.isChecked()

            lib_manager = get_library_manager()
            lib_manager.update_library(self._library)

            self.library_updated.emit(self._library.id)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")


class LibraryScanDialog(QDialog):
    """Dialog for scanning a library."""

    scan_completed = Signal(int, int, int)  # added, updated, missing

    def __init__(self, library: Library, incremental: bool = True, parent=None):
        super().__init__(parent)
        self._library = library
        self._incremental = incremental
        self._scanner: Optional[LibraryScanner] = None

        self.setWindowTitle(f"Scanning: {library.name}")
        self.setMinimumWidth(400)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Status label
        self._status_label = QLabel("Preparing to scan...")
        layout.addWidget(self._status_label)

        # Current file label
        self._file_label = QLabel("")
        self._file_label.setWordWrap(True)
        self._file_label.setStyleSheet("color: gray;")
        layout.addWidget(self._file_label)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        layout.addWidget(self._progress)

        # Cancel button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel_scan)
        btn_layout.addWidget(self._cancel_btn)

        layout.addLayout(btn_layout)

    def showEvent(self, event) -> None:
        """Start scanning when dialog is shown."""
        super().showEvent(event)
        self._start_scan()

    def _start_scan(self) -> None:
        """Start the scan."""
        self._scanner = LibraryScanner(
            self._library.id,
            incremental=self._incremental,
            parent=self,
        )
        self._scanner.progress.connect(self._on_progress)
        self._scanner.finished_scan.connect(self._on_finished)
        self._scanner.error.connect(self._on_error)
        self._scanner.start()

    def _on_progress(self, current: int, total: int, filename: str) -> None:
        """Handle progress update."""
        percent = int((current / total) * 100) if total > 0 else 0
        self._progress.setValue(percent)
        self._status_label.setText(f"Scanning: {current} / {total}")
        self._file_label.setText(filename)

    def _on_finished(self, added: int, updated: int, missing: int) -> None:
        """Handle scan completion."""
        self.scan_completed.emit(added, updated, missing)

        # Show summary
        msg = f"Scan complete!\n\nAdded: {added}\nUpdated: {updated}"
        if missing > 0:
            msg += f"\nMissing: {missing}"

        QMessageBox.information(self, "Scan Complete", msg)
        self.accept()

    def _on_error(self, error: str) -> None:
        """Handle scan error."""
        QMessageBox.critical(self, "Scan Error", error)
        self.reject()

    def _cancel_scan(self) -> None:
        """Cancel the scan."""
        if self._scanner and self._scanner.isRunning():
            self._scanner.cancel()
            self._scanner.wait()
        self.reject()

    def closeEvent(self, event) -> None:
        """Handle close event."""
        self._cancel_scan()
        super().closeEvent(event)


class LibraryManagerDialog(QDialog):
    """Dialog for managing all libraries."""

    library_selected = Signal(int)  # library_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Asset Libraries")
        self.setMinimumSize(500, 400)
        self._setup_ui()
        self._load_libraries()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Library list
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list)

        # Buttons
        btn_layout = QHBoxLayout()

        add_btn = QPushButton("Add Library...")
        add_btn.clicked.connect(self._add_library)
        btn_layout.addWidget(add_btn)

        self._edit_btn = QPushButton("Edit...")
        self._edit_btn.clicked.connect(self._edit_library)
        self._edit_btn.setEnabled(False)
        btn_layout.addWidget(self._edit_btn)

        self._scan_btn = QPushButton("Rescan")
        self._scan_btn.clicked.connect(self._scan_library)
        self._scan_btn.setEnabled(False)
        btn_layout.addWidget(self._scan_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._delete_library)
        self._delete_btn.setEnabled(False)
        btn_layout.addWidget(self._delete_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        # Connect selection
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

    def _load_libraries(self) -> None:
        """Load library list."""
        self._list.clear()

        lib_manager = get_library_manager()
        libraries = lib_manager.get_all_libraries()

        for lib in libraries:
            stats = lib_manager.get_library_stats(lib.id)
            text = f"{lib.name}\n{lib.root_path}\n{stats['total_assets']} assets"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, lib.id)
            self._list.addItem(item)

    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        has_selection = bool(self._list.selectedItems())
        self._edit_btn.setEnabled(has_selection)
        self._scan_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle item double-click."""
        library_id = item.data(Qt.ItemDataRole.UserRole)
        self.library_selected.emit(library_id)
        self.accept()

    def _add_library(self) -> None:
        """Add a new library."""
        dialog = LibraryCreateDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_libraries()

    def _edit_library(self) -> None:
        """Edit selected library."""
        items = self._list.selectedItems()
        if not items:
            return

        library_id = items[0].data(Qt.ItemDataRole.UserRole)
        lib_manager = get_library_manager()
        library = lib_manager.get_library(library_id)

        if library:
            dialog = LibraryEditDialog(library, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._load_libraries()

    def _scan_library(self) -> None:
        """Rescan selected library."""
        items = self._list.selectedItems()
        if not items:
            return

        library_id = items[0].data(Qt.ItemDataRole.UserRole)
        lib_manager = get_library_manager()
        library = lib_manager.get_library(library_id)

        if library:
            dialog = LibraryScanDialog(library, incremental=False, parent=self)
            dialog.exec()
            self._load_libraries()

    def _delete_library(self) -> None:
        """Delete selected library."""
        items = self._list.selectedItems()
        if not items:
            return

        library_id = items[0].data(Qt.ItemDataRole.UserRole)
        lib_manager = get_library_manager()
        library = lib_manager.get_library(library_id)

        if not library:
            return

        reply = QMessageBox.question(
            self,
            "Delete Library",
            f"Delete library '{library.name}'?\n\n"
            "This will remove all metadata. Files on disk will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            lib_manager.delete_library(library_id)
            self._load_libraries()
