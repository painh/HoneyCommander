"""File search dialog."""

import fnmatch
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
    QSplitter,
    QWidget,
)

from commander.views.preview_panel import PreviewPanel


class SearchWorker(QThread):
    """Background worker for file search."""

    # Use str instead of Path for cross-thread signal safety
    result_found = Signal(str)
    search_finished = Signal()

    def __init__(self, root_path: Path, pattern: str, recursive: bool = True):
        super().__init__()
        self._root_path = root_path
        self._pattern = pattern.lower()
        self._recursive = recursive
        self._stopped = False
        # Check if pattern uses wildcards
        self._use_glob = "*" in pattern or "?" in pattern

    def run(self):
        """Run the search."""
        try:
            if self._recursive:
                self._search_recursive(self._root_path)
            else:
                self._search_flat(self._root_path)
        except Exception as e:
            print(f"Search error: {e}")
        finally:
            self.search_finished.emit()

    def _matches(self, name: str) -> bool:
        """Check if name matches the pattern."""
        name_lower = name.lower()
        if self._use_glob:
            # Use fnmatch for wildcard patterns
            return fnmatch.fnmatch(name_lower, self._pattern)
        else:
            # Simple substring match
            return self._pattern in name_lower

    def _search_recursive(self, path: Path):
        """Search recursively."""
        if self._stopped:
            return

        try:
            for item in path.iterdir():
                if self._stopped:
                    return

                if self._matches(item.name):
                    self.result_found.emit(str(item))

                if item.is_dir():
                    self._search_recursive(item)
        except (PermissionError, OSError):
            pass

    def _search_flat(self, path: Path):
        """Search only in current directory."""
        try:
            for item in path.iterdir():
                if self._stopped:
                    return

                if self._matches(item.name):
                    self.result_found.emit(str(item))
        except (PermissionError, OSError):
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
        self.resize(800, 500)

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)

        # Search path label
        path_label = QLabel(f"검색 위치: {self._root_path}")
        path_label.setStyleSheet("color: #888; font-size: 11px;")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # Search input
        search_layout = QHBoxLayout()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("검색어 입력 (예: *.png, test*.txt, photo??.jpg)")
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_input.returnPressed.connect(self._select_first_result)
        search_layout.addWidget(self._search_input)

        layout.addLayout(search_layout)

        # Help text
        help_label = QLabel("* = 여러 문자, ? = 한 문자 (예: *.jpg, test*.png, img??.gif)")
        help_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(help_label)

        # Options
        options_layout = QHBoxLayout()

        self._recursive_check = QCheckBox("Search in subfolders")
        self._recursive_check.setChecked(True)
        options_layout.addWidget(self._recursive_check)

        self._status_label = QLabel("")
        options_layout.addWidget(self._status_label, stretch=1)

        layout.addLayout(options_layout)

        # Splitter: Results list + Preview panel
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Results list
        self._results_list = QListWidget()
        self._results_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._results_list.itemClicked.connect(self._on_item_clicked)
        self._results_list.currentItemChanged.connect(self._on_current_item_changed)
        splitter.addWidget(self._results_list)

        # Right: Preview panel
        self._preview_panel = PreviewPanel()
        splitter.addWidget(self._preview_panel)

        # Set splitter sizes (2:1 ratio)
        splitter.setSizes([500, 250])

        layout.addWidget(splitter, stretch=1)

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

    def _on_result_found(self, path_str: str):
        """Handle search result."""
        # Limit results
        if self._results_list.count() >= 100:
            return

        path = Path(path_str)
        item = QListWidgetItem()

        try:
            item.setText(str(path.relative_to(self._root_path)))
        except ValueError:
            item.setText(path_str)

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

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle click on result - show preview."""
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._preview_panel.show_preview(path)

    def _on_current_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle current item change (keyboard navigation) - show preview."""
        if current:
            path = current.data(Qt.ItemDataRole.UserRole)
            if path:
                self._preview_panel.show_preview(path)

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
