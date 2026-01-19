"""Grid overlay widget for image viewer."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor


class GridOverlay(QWidget):
    """Transparent overlay widget that draws a grid over the image."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._grid_size = 16
        self._visible = False

    def set_grid_size(self, size: int) -> None:
        """Set grid cell size in pixels."""
        self._grid_size = max(4, size)
        if self._visible:
            self.update()

    def grid_size(self) -> int:
        """Get current grid size."""
        return self._grid_size

    def set_grid_visible(self, visible: bool) -> None:
        """Show or hide the grid."""
        self._visible = visible
        self.setVisible(visible)
        if visible:
            self.update()

    def is_grid_visible(self) -> bool:
        """Check if grid is visible."""
        return self._visible

    def paintEvent(self, event) -> None:
        """Draw the grid."""
        if not self._visible:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Semi-transparent cyan grid
        pen = QPen(QColor(0, 255, 255, 100))
        pen.setWidth(1)
        painter.setPen(pen)

        w, h = self.width(), self.height()
        size = self._grid_size

        # Draw vertical lines
        x = 0
        while x <= w:
            painter.drawLine(x, 0, x, h)
            x += size

        # Draw horizontal lines
        y = 0
        while y <= h:
            painter.drawLine(0, y, w, y)
            y += size

        painter.end()
