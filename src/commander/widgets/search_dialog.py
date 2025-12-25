"""File search dialog."""

from pathlib import Path
from typing import Generator

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QCheckBox,
)


class SearchWorker(QThread):
    """Background worker for file search."""

    result_found = Signal(Path)
    search_finished = Signal()

    def __init__(self, root_path: Path, pattern: str, recursive: bool = True):
        super().__init__()
        self._root_path = root_path
        self._pattern = pattern.lower()
        self._recursive = recursive
        self._stopped = False

    def run(self):
        """Run the search."""
        try:
            if self._recursive:
                self._search_recursive(self._root_path)
            else:
                self._search_flat(self._root_path)
        except Exception:
            pass
        finally:
            self.search_finished.emit()

    def _search_recursive(self, path: Path):
        """Search recursively."""
        if self._stopped:
            return

        try:
            for item in path.iterdir():
                if self._stopped:
                    return

                if self._pattern in item.name.lower():
                    self.result_found.emit(item)

                if item.is_dir():
                    self._search_recursive(item)
        except PermissionError:
            pass

    def _search_flat(self, path: Path):
        """Search only in current directory."""
        try:
            for item in path.iterdir():
                if self._stopped:
                    return

                if self._pattern in item.name.lower():
                    self.result_found.emit(item)
        except PermissionError:
            pass

    def stop(self):
        """Stop the search."""
        self._stopped = True


class SearchDialog(QDialog):
    """Dialog for searching files by name."""

    def __init__(self, root_path: Path, parent=None):
        super().__init__(parent)
        self._root_path = root_path
        self._selected_path: Path | None = None
        self._worker: SearchWorker | None = None

        self._setup_ui()
        self.setWindowTitle("Search Files (F3)")
        self.resize(500, 400)

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)

        # Search input
        search_layout = QHBoxLayout()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Enter filename to search...")
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_input.returnPressed.connect(self._select_first_result)
        search_layout.addWidget(self._search_input)

        layout.addLayout(search_layout)

        # Options
        options_layout = QHBoxLayout()

        self._recursive_check = QCheckBox("Search in subfolders")
        self._recursive_check.setChecked(True)
        options_layout.addWidget(self._recursive_check)

        self._status_label = QLabel("")
        options_layout.addWidget(self._status_label, stretch=1)

        layout.addLayout(options_layout)

        # Results list
        self._results_list = QListWidget()
        self._results_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._results_list, stretch=1)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._go_button = QPushButton("Go to")
        self._go_button.clicked.connect(self._accept_selection)
        self._go_button.setEnabled(False)
        button_layout.addWidget(self._go_button)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        layout.addLayout(button_layout)

        # Focus search input
        self._search_input.setFocus()

    def _on_search_text_changed(self, text: str):
        """Handle search text change."""
        # Stop previous search
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait()

        self._results_list.clear()
        self._go_button.setEnabled(False)

        if len(text) < 1:
            self._status_label.setText("")
            return

        # Start new search
        self._status_label.setText("Searching...")
        self._worker = SearchWorker(
            self._root_path, text, self._recursive_check.isChecked()
        )
        self._worker.result_found.connect(self._on_result_found)
        self._worker.search_finished.connect(self._on_search_finished)
        self._worker.start()

    def _on_result_found(self, path: Path):
        """Handle search result."""
        # Limit results
        if self._results_list.count() >= 100:
            return

        item = QListWidgetItem()
        item.setText(str(path.relative_to(self._root_path)))
        item.setData(Qt.ItemDataRole.UserRole, path)

        # Set icon
        if path.is_dir():
            item.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_DirIcon
            ))
        else:
            item.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_FileIcon
            ))

        self._results_list.addItem(item)
        self._go_button.setEnabled(True)

    def _on_search_finished(self):
        """Handle search completion."""
        count = self._results_list.count()
        if count >= 100:
            self._status_label.setText(f"Found 100+ results (showing first 100)")
        else:
            self._status_label.setText(f"Found {count} result(s)")

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double click on result."""
        self._selected_path = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _select_first_result(self):
        """Select first result and accept."""
        if self._results_list.count() > 0:
            item = self._results_list.item(0)
            self._selected_path = item.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def _accept_selection(self):
        """Accept current selection."""
        current = self._results_list.currentItem()
        if current:
            self._selected_path = current.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def get_selected_path(self) -> Path | None:
        """Get the selected path."""
        return self._selected_path

    def closeEvent(self, event):
        """Clean up on close."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait()
        super().closeEvent(event)
