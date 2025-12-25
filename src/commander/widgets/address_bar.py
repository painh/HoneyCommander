"""Address bar widget."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit


class AddressBar(QWidget):
    """Address bar showing current path."""

    path_changed = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Enter path...")
        self._path_edit.returnPressed.connect(self._on_return_pressed)

        layout.addWidget(self._path_edit)

    def set_path(self, path: Path):
        """Set displayed path."""
        self._path_edit.setText(str(path))

    def _on_return_pressed(self):
        """Handle return key press."""
        path = Path(self._path_edit.text())
        if path.exists() and path.is_dir():
            self.path_changed.emit(path)
