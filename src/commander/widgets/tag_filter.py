"""Tag filtering widget for Asset Manager."""

from typing import Optional, Set

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QCheckBox,
    QFrame,
    QPushButton,
    QSizePolicy,
)

from ..core.asset_manager import Tag, get_tag_manager


class TagCheckBox(QCheckBox):
    """Checkbox for a single tag with usage count."""

    def __init__(self, tag: Tag, count: int = 0, parent=None):
        super().__init__(parent)
        self.tag = tag
        self.count = count
        self._update_text()

        # Optional color indicator
        if tag.color:
            self.setStyleSheet(f"QCheckBox {{ color: {tag.color}; }}")

    def _update_text(self) -> None:
        """Update checkbox text with count."""
        if self.count > 0:
            self.setText(f"{self.tag.full_name} ({self.count})")
        else:
            self.setText(self.tag.full_name)

    def set_count(self, count: int) -> None:
        """Update usage count."""
        self.count = count
        self._update_text()


class TagFilterWidget(QWidget):
    """Widget for filtering assets by tags.

    Displays a list of tags with checkboxes. Checking a tag filters
    the asset list to show only assets with that tag.

    Signals:
        filter_changed: Emitted when selected tags change (list of tag_ids)
    """

    filter_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._library_id: Optional[int] = None
        self._tag_checkboxes: dict[int, TagCheckBox] = {}
        self._selected_tag_ids: Set[int] = set()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header_layout = QHBoxLayout()

        header_label = QLabel("Tags")
        header_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(header_label)

        header_layout.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(20)
        self._clear_btn.clicked.connect(self.clear_selection)
        self._clear_btn.hide()  # Hidden when no selection
        header_layout.addWidget(self._clear_btn)

        layout.addLayout(header_layout)

        # Search input
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter tags...")
        self._search_edit.textChanged.connect(self._filter_tags)
        self._search_edit.setClearButtonEnabled(True)
        layout.addWidget(self._search_edit)

        # Scrollable tag list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._tag_container = QWidget()
        self._tag_layout = QVBoxLayout(self._tag_container)
        self._tag_layout.setContentsMargins(0, 0, 0, 0)
        self._tag_layout.setSpacing(2)
        self._tag_layout.addStretch()

        scroll.setWidget(self._tag_container)
        layout.addWidget(scroll, 1)

        # Empty state label
        self._empty_label = QLabel("No tags in this library")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: gray;")
        self._empty_label.hide()
        layout.addWidget(self._empty_label)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(100)

    def set_library(self, library_id: Optional[int]) -> None:
        """Set the current library and load its tags."""
        self._library_id = library_id
        self._selected_tag_ids.clear()
        self._load_tags()
        self._update_clear_button()

    def _load_tags(self) -> None:
        """Load tags for current library."""
        # Clear existing checkboxes
        for cb in self._tag_checkboxes.values():
            cb.deleteLater()
        self._tag_checkboxes.clear()

        if self._library_id is None:
            self._empty_label.show()
            return

        tag_manager = get_tag_manager()

        # Get tags used in this library
        tags = tag_manager.get_library_tags(self._library_id)
        counts = tag_manager.get_library_tag_counts(self._library_id)

        if not tags:
            self._empty_label.show()
            return

        self._empty_label.hide()

        # Group by namespace
        namespaces: dict[str, list[tuple[Tag, int]]] = {}
        for tag in tags:
            ns = tag.namespace or ""
            if ns not in namespaces:
                namespaces[ns] = []
            namespaces[ns].append((tag, counts.get(tag.id, 0)))

        # Add tags to layout (insert before stretch)
        insert_index = 0

        for namespace in sorted(namespaces.keys()):
            # Add namespace header if not empty
            if namespace:
                ns_label = QLabel(namespace)
                ns_label.setStyleSheet("font-weight: bold; color: gray; margin-top: 4px;")
                self._tag_layout.insertWidget(insert_index, ns_label)
                insert_index += 1

            # Add tags
            for tag, count in sorted(namespaces[namespace], key=lambda x: x[0].name):
                cb = TagCheckBox(tag, count)
                cb.stateChanged.connect(lambda state, t=tag: self._on_tag_toggled(t, state))
                self._tag_checkboxes[tag.id] = cb
                self._tag_layout.insertWidget(insert_index, cb)
                insert_index += 1

    def _on_tag_toggled(self, tag: Tag, state: int) -> None:
        """Handle tag checkbox toggle."""
        if state == Qt.CheckState.Checked.value:
            self._selected_tag_ids.add(tag.id)
        else:
            self._selected_tag_ids.discard(tag.id)

        self._update_clear_button()
        self.filter_changed.emit(list(self._selected_tag_ids))

    def _filter_tags(self, text: str) -> None:
        """Filter visible tags by search text."""
        text = text.lower()

        for tag_id, cb in self._tag_checkboxes.items():
            visible = not text or text in cb.tag.full_name.lower()
            cb.setVisible(visible)

    def _update_clear_button(self) -> None:
        """Show/hide clear button based on selection."""
        self._clear_btn.setVisible(len(self._selected_tag_ids) > 0)

    def clear_selection(self) -> None:
        """Clear all selected tags."""
        for cb in self._tag_checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)

        self._selected_tag_ids.clear()
        self._update_clear_button()
        self.filter_changed.emit([])

    def get_selected_tag_ids(self) -> list[int]:
        """Get list of selected tag IDs."""
        return list(self._selected_tag_ids)

    def set_selected_tag_ids(self, tag_ids: list[int]) -> None:
        """Set selected tags programmatically."""
        self._selected_tag_ids = set(tag_ids)

        for tag_id, cb in self._tag_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(tag_id in self._selected_tag_ids)
            cb.blockSignals(False)

        self._update_clear_button()

    def refresh(self) -> None:
        """Refresh tag list and counts."""
        # Remember selection
        selected = self._selected_tag_ids.copy()

        self._load_tags()

        # Restore selection
        self._selected_tag_ids = selected
        for tag_id in selected:
            if tag_id in self._tag_checkboxes:
                self._tag_checkboxes[tag_id].blockSignals(True)
                self._tag_checkboxes[tag_id].setChecked(True)
                self._tag_checkboxes[tag_id].blockSignals(False)

        self._update_clear_button()
