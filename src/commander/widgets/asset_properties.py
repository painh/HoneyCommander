"""Asset properties panel for editing asset metadata."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QFrame,
    QCompleter,
)
from PySide6.QtGui import QPixmap

from ..core.asset_manager import Asset, get_library_manager, get_tag_manager


class StarRating(QWidget):
    """Star rating widget."""

    rating_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rating = 0
        self._buttons: list[QPushButton] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        for i in range(5):
            btn = QPushButton("☆")
            btn.setFixedSize(24, 24)
            btn.setFlat(True)
            btn.setStyleSheet("font-size: 16px; border: none;")
            btn.clicked.connect(lambda checked, r=i + 1: self._on_star_clicked(r))
            self._buttons.append(btn)
            layout.addWidget(btn)

        # Clear button
        clear_btn = QPushButton("×")
        clear_btn.setFixedSize(20, 20)
        clear_btn.setToolTip("Clear rating")
        clear_btn.clicked.connect(lambda: self._on_star_clicked(0))
        layout.addWidget(clear_btn)

        layout.addStretch()

    def _on_star_clicked(self, rating: int) -> None:
        self.set_rating(rating)
        self.rating_changed.emit(rating)

    def set_rating(self, rating: int) -> None:
        self._rating = rating
        for i, btn in enumerate(self._buttons):
            btn.setText("★" if i < rating else "☆")

    def get_rating(self) -> int:
        return self._rating


class TagEditor(QWidget):
    """Tag editing widget with add/remove functionality."""

    tags_changed = Signal(list)  # list of tag strings

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tags: list[str] = []
        self._library_id: Optional[int] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Tag display area
        self._tags_label = QLabel()
        self._tags_label.setWordWrap(True)
        self._tags_label.setStyleSheet("color: #666;")
        layout.addWidget(self._tags_label)

        # Add tag input
        input_layout = QHBoxLayout()

        self._tag_input = QLineEdit()
        self._tag_input.setPlaceholderText("Add tag (e.g., 'character:player')")
        self._tag_input.returnPressed.connect(self._add_tag)
        input_layout.addWidget(self._tag_input)

        add_btn = QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.clicked.connect(self._add_tag)
        input_layout.addWidget(add_btn)

        layout.addLayout(input_layout)

        self._update_display()

    def set_library(self, library_id: Optional[int]) -> None:
        """Set library for tag autocomplete."""
        self._library_id = library_id
        self._setup_completer()

    def _setup_completer(self) -> None:
        """Setup tag autocomplete."""
        if self._library_id is None:
            self._tag_input.setCompleter(None)
            return

        tag_manager = get_tag_manager()
        tags = tag_manager.get_library_tags(self._library_id)
        tag_names = [t.full_name for t in tags]

        completer = QCompleter(tag_names, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._tag_input.setCompleter(completer)

    def set_tags(self, tags: list[str]) -> None:
        """Set current tags."""
        self._tags = list(tags)
        self._update_display()

    def get_tags(self) -> list[str]:
        """Get current tags."""
        return list(self._tags)

    def _update_display(self) -> None:
        """Update tag display."""
        if self._tags:
            # Create clickable-looking tag display
            display = " ".join([f"[{t}]" for t in self._tags])
            self._tags_label.setText(display)
        else:
            self._tags_label.setText("(no tags)")

    def _add_tag(self) -> None:
        """Add a new tag."""
        tag_text = self._tag_input.text().strip()
        if not tag_text:
            return

        if tag_text not in self._tags:
            self._tags.append(tag_text)
            self._update_display()
            self.tags_changed.emit(self._tags)

        self._tag_input.clear()

    def remove_tag(self, tag: str) -> None:
        """Remove a tag."""
        if tag in self._tags:
            self._tags.remove(tag)
            self._update_display()
            self.tags_changed.emit(self._tags)


class AssetPropertiesPanel(QWidget):
    """Panel for viewing and editing asset properties.

    Signals:
        asset_updated: Emitted when asset is modified (asset_id)
    """

    asset_updated = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._asset: Optional[Asset] = None
        self._library_id: Optional[int] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # Preview image
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(150)
        self._preview_label.setMaximumHeight(200)
        self._preview_label.setStyleSheet("background: #f0f0f0; border-radius: 4px;")
        content_layout.addWidget(self._preview_label)

        # File name
        self._name_label = QLabel()
        self._name_label.setWordWrap(True)
        self._name_label.setStyleSheet("font-weight: bold;")
        content_layout.addWidget(self._name_label)

        # Rating
        rating_container = QWidget()
        rating_layout = QHBoxLayout(rating_container)
        rating_layout.setContentsMargins(0, 0, 0, 0)
        rating_label = QLabel("Rating:")
        rating_layout.addWidget(rating_label)
        self._rating_widget = StarRating()
        self._rating_widget.rating_changed.connect(self._on_rating_changed)
        rating_layout.addWidget(self._rating_widget)
        rating_layout.addStretch()
        content_layout.addWidget(rating_container)

        # Tags
        tags_label = QLabel("Tags:")
        content_layout.addWidget(tags_label)
        self._tag_editor = TagEditor()
        self._tag_editor.tags_changed.connect(self._on_tags_changed)
        content_layout.addWidget(self._tag_editor)

        # Notes
        notes_label = QLabel("Notes:")
        content_layout.addWidget(notes_label)
        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setMaximumHeight(100)
        self._notes_edit.setPlaceholderText("Add notes about this asset...")
        self._notes_edit.textChanged.connect(self._on_notes_changed)
        content_layout.addWidget(self._notes_edit)

        # File info
        info_frame = QFrame()
        info_frame.setStyleSheet("background: #f8f8f8; border-radius: 4px; padding: 4px;")
        info_layout = QFormLayout(info_frame)
        info_layout.setContentsMargins(8, 8, 8, 8)

        self._path_label = QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setStyleSheet("color: gray;")
        info_layout.addRow("Path:", self._path_label)

        self._size_label = QLabel()
        info_layout.addRow("Size:", self._size_label)

        self._hash_label = QLabel()
        self._hash_label.setStyleSheet("color: gray; font-family: monospace; font-size: 10px;")
        info_layout.addRow("Hash:", self._hash_label)

        content_layout.addWidget(info_frame)

        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Empty state
        self._empty_label = QLabel("Select an asset to view properties")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: gray;")
        layout.addWidget(self._empty_label)

        # Initial state
        scroll.hide()
        self._content_scroll = scroll

    def set_library(self, library_id: Optional[int]) -> None:
        """Set current library for tag autocomplete."""
        self._library_id = library_id
        self._tag_editor.set_library(library_id)

    def set_asset(self, asset: Optional[Asset]) -> None:
        """Set the asset to display."""
        self._asset = asset

        if asset is None:
            self._content_scroll.hide()
            self._empty_label.show()
            return

        self._empty_label.hide()
        self._content_scroll.show()

        # Update UI
        self._name_label.setText(asset.original_filename)
        self._rating_widget.set_rating(asset.rating)
        self._tag_editor.set_tags(asset.tags)

        # Notes (block signals to avoid triggering save)
        self._notes_edit.blockSignals(True)
        self._notes_edit.setPlainText(asset.notes or "")
        self._notes_edit.blockSignals(False)

        # File info
        if asset.current_path:
            self._path_label.setText(str(asset.current_path))
        else:
            self._path_label.setText("(missing)")

        self._size_label.setText(self._format_size(asset.file_size))
        self._hash_label.setText(asset.partial_hash[:16] + "...")

        # Load preview image
        self._load_preview()

    def _load_preview(self) -> None:
        """Load preview image."""
        if self._asset is None or self._asset.current_path is None:
            self._preview_label.setText("No preview")
            return

        path = self._asset.current_path
        if not path.exists():
            self._preview_label.setText("File missing")
            return

        # Check if it's an image
        ext = path.suffix.lower()
        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

        if ext in image_exts:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._preview_label.setPixmap(scaled)
                return

        # Non-image or failed to load
        self._preview_label.setText(f"[{ext[1:].upper()}]")

    def _format_size(self, size: int) -> str:
        """Format file size."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def _on_rating_changed(self, rating: int) -> None:
        """Handle rating change."""
        if self._asset is None:
            return

        lib_manager = get_library_manager()
        lib_manager.update_asset(self._asset.id, rating=rating)
        self._asset.rating = rating
        self.asset_updated.emit(self._asset.id)

    def _on_tags_changed(self, tags: list[str]) -> None:
        """Handle tags change."""
        if self._asset is None:
            return

        lib_manager = get_library_manager()
        tag_manager = get_tag_manager()

        # Get current tag IDs
        current_tag_ids = set(lib_manager.get_asset_tag_ids(self._asset.id))

        # Get new tag IDs (creating tags as needed)
        new_tag_ids = set()
        for tag_str in tags:
            tag = tag_manager.get_or_create_from_string(tag_str)
            new_tag_ids.add(tag.id)

        # Add new tags
        for tag_id in new_tag_ids - current_tag_ids:
            lib_manager.add_tag_to_asset(self._asset.id, tag_id)

        # Remove old tags
        for tag_id in current_tag_ids - new_tag_ids:
            lib_manager.remove_tag_from_asset(self._asset.id, tag_id)

        self._asset.tags = tags
        self.asset_updated.emit(self._asset.id)

    def _on_notes_changed(self) -> None:
        """Handle notes change."""
        if self._asset is None:
            return

        notes = self._notes_edit.toPlainText()
        lib_manager = get_library_manager()
        lib_manager.update_asset(self._asset.id, notes=notes)
        self._asset.notes = notes
        self.asset_updated.emit(self._asset.id)

    def clear(self) -> None:
        """Clear the panel."""
        self.set_asset(None)
