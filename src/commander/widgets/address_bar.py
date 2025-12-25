"""Address bar widget."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QStyle

from commander.utils.settings import Settings


class AddressBar(QWidget):
    """Address bar showing current path."""

    path_changed = Signal(Path)
    favorite_toggled = Signal(Path, bool)  # path, is_favorite

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path: Path | None = None
        self._settings = Settings()
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Path edit
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Enter path...")
        self._path_edit.returnPressed.connect(self._on_return_pressed)
        layout.addWidget(self._path_edit, stretch=1)

        # Favorite star button
        self._star_btn = QPushButton()
        self._star_btn.setFixedSize(28, 28)
        self._star_btn.setToolTip("Add to favorites")
        self._star_btn.clicked.connect(self._toggle_favorite)
        self._update_star_icon()
        layout.addWidget(self._star_btn)

    def set_path(self, path: Path):
        """Set displayed path."""
        self._current_path = path
        self._path_edit.setText(str(path))
        self._update_star_icon()

    def _on_return_pressed(self):
        """Handle return key press."""
        path = Path(self._path_edit.text())
        if path.exists() and path.is_dir():
            self.path_changed.emit(path)

    def focus_and_select(self):
        """Focus the path edit and select all text."""
        self._path_edit.setFocus()
        self._path_edit.selectAll()

    def _toggle_favorite(self):
        """Toggle current path as favorite."""
        if not self._current_path:
            return

        is_fav = self._settings.is_favorite(self._current_path)
        if is_fav:
            self._settings.remove_favorite(self._current_path)
        else:
            self._settings.add_favorite(self._current_path)

        self._update_star_icon()
        self.favorite_toggled.emit(self._current_path, not is_fav)

    def _update_star_icon(self):
        """Update star button appearance."""
        if self._current_path and self._settings.is_favorite(self._current_path):
            # Filled star (favorite)
            self._star_btn.setText("★")
            self._star_btn.setStyleSheet(
                "QPushButton { color: gold; font-size: 18px; font-weight: bold; }"
            )
            self._star_btn.setToolTip("Remove from favorites")
        else:
            # Empty star (not favorite)
            self._star_btn.setText("☆")
            self._star_btn.setStyleSheet(
                "QPushButton { color: gray; font-size: 18px; }"
            )
            self._star_btn.setToolTip("Add to favorites")
