"""Favorites panel widget."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QMenu,
)

from commander.utils.settings import Settings


class FavoritesPanel(QWidget):
    """Panel showing favorite folders."""

    folder_selected = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = Settings()
        self._setup_ui()
        self._load_favorites()

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Header
        header = QLabel("  ★ Favorites")
        header.setStyleSheet(
            "QLabel { font-weight: bold; padding: 5px; background: palette(midlight); }"
        )
        layout.addWidget(header)

        # List
        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setMaximumHeight(150)
        layout.addWidget(self._list)

    def _load_favorites(self):
        """Load favorites from settings."""
        self._list.clear()
        favorites = self._settings.load_favorites()

        for path in favorites:
            self._add_favorite_item(path)

    def _add_favorite_item(self, path: Path):
        """Add a favorite item to the list."""
        item = QListWidgetItem()
        item.setText(path.name or str(path))
        item.setToolTip(str(path))
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
        self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle item click."""
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and path.exists():
            self.folder_selected.emit(path)

    def _show_context_menu(self, pos):
        """Show context menu for favorites."""
        item = self._list.itemAt(pos)
        if not item:
            return

        path = item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)

        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self.folder_selected.emit(path))

        menu.addSeparator()

        remove_action = menu.addAction("Remove from Favorites")
        remove_action.triggered.connect(lambda: self._remove_favorite(path))

        menu.exec(self._list.mapToGlobal(pos))

    def _remove_favorite(self, path: Path):
        """Remove a favorite."""
        self._settings.remove_favorite(path)
        self._load_favorites()

    def refresh(self):
        """Refresh the favorites list."""
        self._load_favorites()

    def add_favorite(self, path: Path):
        """Add a new favorite."""
        self._settings.add_favorite(path)
        self._load_favorites()

    def remove_favorite(self, path: Path):
        """Remove a favorite."""
        self._settings.remove_favorite(path)
        self._load_favorites()
