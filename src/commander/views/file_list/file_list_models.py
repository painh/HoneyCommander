"""Models and enums for file list view."""

from __future__ import annotations

from pathlib import Path
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtWidgets import QFileSystemModel, QMenu
from PySide6.QtGui import QColor, QBrush, QKeyEvent

from commander.utils.themes import get_file_color

if TYPE_CHECKING:
    from typing import Callable


class ViewMode(Enum):
    """View modes for the file list."""

    LIST = "list"
    ICONS = "icons"
    THUMBNAILS = "thumbnails"


class ColoredFileSystemModel(QFileSystemModel):
    """QFileSystemModel with theme-based file type colors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Enable editing for rename functionality
        self.setReadOnly(False)

    def data(self, index, role: int = Qt.ItemDataRole.DisplayRole):  # type: ignore[override]
        """Override data to provide custom foreground colors."""
        if role == Qt.ItemDataRole.ForegroundRole:
            file_path = Path(self.filePath(index))
            color_hex = get_file_color(file_path)
            if color_hex:
                return QBrush(QColor(color_hex))

        return super().data(index, role)


class MenuShortcutFilter(QObject):
    """Event filter to handle keyboard shortcuts in context menu."""

    def __init__(
        self,
        menu: QMenu,
        shortcut_actions: dict,
        run_command: Callable,
        extract_callback: Callable | None = None,
    ):
        super().__init__(menu)
        self._menu = menu
        self._shortcut_actions = shortcut_actions
        self._run_command = run_command
        self._extract_callback = extract_callback

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event  # type: ignore[assignment]
            text = key_event.text().upper()
            if text in self._shortcut_actions:
                cmd, path = self._shortcut_actions[text]
                self._menu.close()
                if cmd is None and self._extract_callback:
                    # Special case: extract archives (Z shortcut)
                    self._extract_callback(path)
                else:
                    self._run_command(cmd, path)
                return True
        return super().eventFilter(obj, event)
