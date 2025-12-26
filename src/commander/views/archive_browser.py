"""Archive browser window."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QWidget,
)
from PySide6.QtGui import QPixmap

from commander.core.archive_handler import ArchiveManager, ArchiveHandler, ArchiveEntry
from commander.core.image_loader import ALL_IMAGE_FORMATS


class ArchiveBrowser(QDialog):
    """Browser for archive contents."""

    IMAGE_EXTENSIONS = ALL_IMAGE_FORMATS

    def __init__(self, archive_path: Path, parent=None):
        super().__init__(parent)
        self._archive_path = archive_path
        self._handler: ArchiveHandler | None = None
        self._current_path = ""

        self._setup_ui()
        self._open_archive()

        self.setWindowTitle(f"Archive: {archive_path.name}")
        self.resize(900, 600)

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()

        self._path_label = QLabel("/")
        toolbar.addWidget(self._path_label, stretch=1)

        self._up_btn = QPushButton("Up")
        self._up_btn.clicked.connect(self._go_up)
        toolbar.addWidget(self._up_btn)

        self._extract_btn = QPushButton("Extract All")
        self._extract_btn.clicked.connect(self._extract_all)
        toolbar.addWidget(self._extract_btn)

        layout.addLayout(toolbar)

        # Main content
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # File list
        self._file_list = QListWidget()
        self._file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._file_list.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self._file_list)

        # Preview panel
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._preview_label = QLabel("Select an image to preview")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll_area.setWidget(self._preview_label)

        self._info_label = QLabel()
        self._info_label.setWordWrap(True)

        preview_layout.addWidget(self._scroll_area, stretch=3)
        preview_layout.addWidget(self._info_label, stretch=1)

        splitter.addWidget(preview_widget)
        splitter.setSizes([500, 300])

        layout.addWidget(splitter)

    def _open_archive(self):
        """Open the archive."""
        self._handler = ArchiveManager.get_handler(self._archive_path)
        if self._handler:
            self._refresh_list()
        else:
            QMessageBox.critical(self, "Error", "Cannot open archive")
            self.close()

    def _refresh_list(self):
        """Refresh file list."""
        if not self._handler:
            return

        self._file_list.clear()
        self._path_label.setText(f"/{self._current_path}" if self._current_path else "/")

        entries = self._handler.list_entries(self._current_path)

        for entry in entries:
            item = QListWidgetItem()
            item.setText(entry.name)
            item.setData(Qt.ItemDataRole.UserRole, entry)

            # Set icon based on type
            if entry.is_dir:
                item.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
            else:
                item.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))

            self._file_list.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double click."""
        entry: ArchiveEntry = item.data(Qt.ItemDataRole.UserRole)

        if entry.is_dir:
            self._current_path = entry.path
            self._refresh_list()

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle single click - show preview."""
        entry: ArchiveEntry = item.data(Qt.ItemDataRole.UserRole)

        if entry.is_dir:
            self._preview_label.clear()
            self._info_label.setText(f"Folder: {entry.name}")
            return

        # Show file info
        size = self._format_size(entry.size)
        self._info_label.setText(
            f"<b>{entry.name}</b><br>"
            f"Size: {size}<br>"
            f"Compressed: {self._format_size(entry.compressed_size)}"
        )

        # Show image preview if applicable
        suffix = Path(entry.name).suffix.lower()
        if suffix in self.IMAGE_EXTENSIONS:
            self._show_image_preview(entry)
        else:
            self._preview_label.setText("No preview available")

    def _show_image_preview(self, entry: ArchiveEntry):
        """Show image preview from archive."""
        try:
            data = self._handler.read_file(entry.path)
            pixmap = QPixmap()
            pixmap.loadFromData(data)

            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._scroll_area.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._preview_label.setPixmap(scaled)
            else:
                self._preview_label.setText("Cannot load image")
        except Exception as e:
            self._preview_label.setText(f"Error: {e}")

    def _go_up(self):
        """Go to parent directory in archive."""
        if self._current_path:
            parent = str(Path(self._current_path).parent)
            self._current_path = "" if parent == "." else parent
            self._refresh_list()

    def _extract_all(self):
        """Extract all files from archive."""
        dest = QFileDialog.getExistingDirectory(self, "Extract to")
        if dest:
            try:
                # Extract using the handler
                entries = self._handler.list_entries()
                for entry in entries:
                    if not entry.is_dir:
                        self._handler.extract(entry.path, Path(dest))

                QMessageBox.information(self, "Success", f"Extracted to {dest}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Extract failed: {e}")

    def _format_size(self, size: int) -> str:
        """Format file size."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def closeEvent(self, event):
        """Clean up on close."""
        if self._handler:
            self._handler.close()
        super().closeEvent(event)
