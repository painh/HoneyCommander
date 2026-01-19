"""Input event handler mixin for fullscreen viewer."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import QApplication


class ViewerInputHandlerMixin:
    """Mixin providing input event handling for the viewer."""

    # These attributes/methods are expected from the main class
    _anim: object
    _scroll_area: object
    _pan_start: QPoint | None
    _settings: object

    def event(self, event) -> bool:
        """Override to handle Tab key before Qt uses it for focus navigation."""
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            self.keyPressEvent(event)
            return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key.Key_Escape, Qt.Key.Key_X, Qt.Key.Key_F4):
            self.close()
        elif key == Qt.Key.Key_Space:
            if self._anim.is_animated:
                self._toggle_animation()
            else:
                self._next_image()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            if self._anim.is_animated and modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._next_frame()
            else:
                self._next_image()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            if self._anim.is_animated and modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._prev_frame()
            else:
                self._prev_image()
        elif key == Qt.Key.Key_Backspace:
            self._prev_image()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._zoom_in()
        elif key == Qt.Key.Key_Minus:
            self._zoom_out()
        elif key == Qt.Key.Key_0:
            self._zoom_original()
        elif key == Qt.Key.Key_9:
            self._zoom_fit()
        elif key == Qt.Key.Key_1:
            self._zoom_original()
        elif key == Qt.Key.Key_Home:
            self._current_index = 0
            self._reset_transform()
            self._load_current_image()
        elif key == Qt.Key.Key_End:
            self._current_index = self._get_total_images() - 1
            self._reset_transform()
            self._load_current_image()
        elif key == Qt.Key.Key_R:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._rotate_counterclockwise()
            else:
                self._rotate_clockwise()
        elif key == Qt.Key.Key_H:
            self._flip_horizontal()
        elif key == Qt.Key.Key_V:
            self._flip_vertical()
        elif key == Qt.Key.Key_Delete:
            self._delete_current()
        elif key == Qt.Key.Key_Tab:
            self._toggle_file_info()
        elif key == Qt.Key.Key_F2:
            self._open_file_dialog()
        elif key == Qt.Key.Key_F:
            self._open_folder()
        elif key == Qt.Key.Key_U:
            self._set_filter(False)
        elif key == Qt.Key.Key_S:
            self._set_filter(True)
        elif key == Qt.Key.Key_C and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._copy_to_clipboard()
        elif key == Qt.Key.Key_E and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._open_in_editor()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self._open_in_explorer()
            else:
                self._select_image()
        elif key == Qt.Key.Key_Insert:
            if sys.platform == "darwin":
                self._copy_to_photos()
        elif key == Qt.Key.Key_BracketLeft:
            self._prev_folder()
        elif key == Qt.Key.Key_BracketRight:
            self._next_folder()
        elif key == Qt.Key.Key_G:
            self._toggle_grid()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()

        # Check if image is larger than viewport (scrollable)
        vbar = self._scroll_area.verticalScrollBar()
        can_scroll = vbar.maximum() > 0

        if can_scroll:
            # Image is larger than viewport - scroll first
            current_pos = vbar.value()
            if delta > 0:
                # Scrolling up
                if current_pos > vbar.minimum():
                    # Can still scroll up
                    vbar.setValue(current_pos - 100)
                    return
                else:
                    # At top - go to previous image
                    self._prev_image()
            else:
                # Scrolling down
                if current_pos < vbar.maximum():
                    # Can still scroll down
                    vbar.setValue(current_pos + 100)
                    return
                else:
                    # At bottom - go to next image
                    self._next_image()
        else:
            # Image fits in viewport - navigate images directly
            if delta > 0:
                self._prev_image()
            elif delta < 0:
                self._next_image()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pan_start = event.pos()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._toggle_fullscreen()

    def mouseMoveEvent(self, event) -> None:
        if self._pan_start and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            h_bar = self._scroll_area.horizontalScrollBar()
            v_bar = self._scroll_area.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pan_start = None

    def _show_with_saved_mode(self) -> None:
        """Show viewer with saved mode (fullscreen or windowed)."""
        if self._settings.load_viewer_fullscreen():
            self.showFullScreen()
        else:
            # Show in windowed mode
            self.setWindowFlags(Qt.WindowType.Window)
            # Center on screen
            screen = QApplication.primaryScreen()
            if screen:
                screen_geo = screen.availableGeometry()
                self.resize(int(screen_geo.width() * 0.8), int(screen_geo.height() * 0.8))
                self.move(
                    (screen_geo.width() - self.width()) // 2,
                    (screen_geo.height() - self.height()) // 2,
                )
            self.show()
            self.activateWindow()
            self.setFocus()

    def _toggle_fullscreen(self) -> None:
        """Toggle between fullscreen and normal window mode."""
        if self.isFullScreen():
            self.showNormal()
            # Restore window frame
            self.setWindowFlags(Qt.WindowType.Window)
            self.show()
            self._settings.save_viewer_fullscreen(False)
        else:
            self.showFullScreen()
            self._settings.save_viewer_fullscreen(True)
