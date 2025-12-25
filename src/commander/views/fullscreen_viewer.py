"""Fullscreen image viewer."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PySide6.QtGui import QPixmap, QKeyEvent, QWheelEvent, QPainter


class FullscreenImageViewer(QWidget):
    """Fullscreen image viewer with navigation."""

    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._image_list: list[Path] = []
        self._current_index: int = 0
        self._zoom_level: float = 1.0
        self._original_pixmap: QPixmap | None = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        self.setStyleSheet("background-color: black;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._image_label)

        # Info label (bottom)
        self._info_label = QLabel()
        self._info_label.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 128); padding: 5px;"
        )
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._info_label)

    def show_image(self, path: Path, image_list: list[Path] | None = None):
        """Show image and optionally set image list for navigation."""
        self._image_list = image_list or [path]

        try:
            self._current_index = self._image_list.index(path)
        except ValueError:
            self._image_list = [path]
            self._current_index = 0

        self._zoom_level = 1.0
        self._load_current_image()
        self.showFullScreen()

    def _load_current_image(self):
        """Load and display current image."""
        if not self._image_list:
            return

        path = self._image_list[self._current_index]
        self._original_pixmap = QPixmap(str(path))

        if self._original_pixmap.isNull():
            self._image_label.setText(f"Cannot load: {path.name}")
            return

        self._update_display()
        self._update_info()

    def _update_display(self):
        """Update displayed image with current zoom."""
        if self._original_pixmap is None or self._original_pixmap.isNull():
            return

        screen_size = QApplication.primaryScreen().size()

        if self._zoom_level == 1.0:
            # Fit to screen
            scaled = self._original_pixmap.scaled(
                screen_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            # Apply zoom
            new_size = QSize(
                int(self._original_pixmap.width() * self._zoom_level),
                int(self._original_pixmap.height() * self._zoom_level),
            )
            scaled = self._original_pixmap.scaled(
                new_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self._image_label.setPixmap(scaled)

    def _update_info(self):
        """Update info label."""
        if not self._image_list:
            return

        path = self._image_list[self._current_index]
        total = len(self._image_list)
        current = self._current_index + 1
        zoom_percent = int(self._zoom_level * 100)

        self._info_label.setText(
            f"{path.name} | {current}/{total} | {zoom_percent}% | "
            f"ESC: close | Arrow keys: navigate | +/-: zoom"
        )

    def _next_image(self):
        """Go to next image."""
        if self._current_index < len(self._image_list) - 1:
            self._current_index += 1
            self._zoom_level = 1.0
            self._load_current_image()

    def _prev_image(self):
        """Go to previous image."""
        if self._current_index > 0:
            self._current_index -= 1
            self._zoom_level = 1.0
            self._load_current_image()

    def _zoom_in(self):
        """Zoom in."""
        if self._zoom_level < 5.0:
            self._zoom_level *= 1.25
            self._update_display()
            self._update_info()

    def _zoom_out(self):
        """Zoom out."""
        if self._zoom_level > 0.1:
            self._zoom_level /= 1.25
            self._update_display()
            self._update_info()

    def _zoom_reset(self):
        """Reset zoom to fit screen."""
        self._zoom_level = 1.0
        self._update_display()
        self._update_info()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard input."""
        key = event.key()

        if key == Qt.Key.Key_Escape:
            self.close()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Space, Qt.Key.Key_PageDown):
            self._next_image()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Backspace, Qt.Key.Key_PageUp):
            self._prev_image()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._zoom_in()
        elif key == Qt.Key.Key_Minus:
            self._zoom_out()
        elif key == Qt.Key.Key_0:
            self._zoom_reset()
        elif key == Qt.Key.Key_Home:
            self._current_index = 0
            self._zoom_level = 1.0
            self._load_current_image()
        elif key == Qt.Key.Key_End:
            self._current_index = len(self._image_list) - 1
            self._zoom_level = 1.0
            self._load_current_image()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zoom."""
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom_in()
        elif delta < 0:
            self._zoom_out()

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Click on left half -> previous, right half -> next
            if event.position().x() < self.width() / 2:
                self._prev_image()
            else:
                self._next_image()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()

    def closeEvent(self, event):
        """Handle close."""
        self.closed.emit()
        super().closeEvent(event)
