"""Custom tab bar with drag-to-detach and drop-to-merge support."""

import json

from PySide6.QtCore import (
    Qt, Signal, QPoint, QMimeData, QSize,
    QPropertyAnimation, Property, QEasingCurve, QRect
)
from PySide6.QtWidgets import QTabBar, QMenu, QApplication, QWidget
from PySide6.QtGui import (
    QDrag, QMouseEvent, QDragEnterEvent, QDropEvent, QDragLeaveEvent,
    QPixmap, QPainter, QColor, QPen
)


# Custom MIME type for tab transfer
TAB_MIME_TYPE = "application/x-commander-tab"

# Distance threshold for triggering tab detach
DETACH_THRESHOLD = 50

# Tab styling
TAB_STYLESHEET = """
QTabBar {
    background: transparent;
    border: none;
}

QTabBar::tab {
    background: #3c3c3c;
    color: #cccccc;
    border: 1px solid #555555;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
    min-width: 120px;
    max-width: 200px;
}

QTabBar::tab:selected {
    background: #2d2d2d;
    color: #ffffff;
    border-color: #007acc;
    border-bottom: 2px solid #007acc;
}

QTabBar::tab:hover:!selected {
    background: #454545;
}

QTabBar::close-button {
    image: url(close.png);
    subcontrol-position: right;
    padding: 2px;
}

QTabBar::close-button:hover {
    background: #ff5555;
    border-radius: 3px;
}
"""


class DropIndicator(QWidget):
    """Animated drop indicator that shows where a tab will be inserted."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 1.0
        self._glow_intensity = 0.0

        # Setup animation for pulsing glow effect
        self._glow_animation = QPropertyAnimation(self, b"glow_intensity")
        self._glow_animation.setDuration(600)
        self._glow_animation.setStartValue(0.3)
        self._glow_animation.setEndValue(1.0)
        self._glow_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._glow_animation.setLoopCount(-1)  # Infinite loop

        # Make it ping-pong (forward then backward)
        self._glow_animation.finished.connect(self._reverse_animation)

        self.setFixedWidth(4)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def _reverse_animation(self):
        """Reverse the animation direction for ping-pong effect."""
        start = self._glow_animation.startValue()
        end = self._glow_animation.endValue()
        self._glow_animation.setStartValue(end)
        self._glow_animation.setEndValue(start)
        self._glow_animation.start()

    def _get_glow_intensity(self) -> float:
        return self._glow_intensity

    def _set_glow_intensity(self, value: float):
        self._glow_intensity = value
        self.update()

    glow_intensity = Property(float, _get_glow_intensity, _set_glow_intensity)

    def start_animation(self):
        """Start the pulsing glow animation."""
        self._glow_animation.setStartValue(0.3)
        self._glow_animation.setEndValue(1.0)
        self._glow_animation.start()
        self.show()

    def stop_animation(self):
        """Stop the animation and hide."""
        self._glow_animation.stop()
        self.hide()

    def paintEvent(self, event):
        """Draw the glowing drop indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Base color - bright cyan/blue
        base_color = QColor(0, 172, 240)  # #00ACF0

        # Calculate glow color based on intensity
        glow_alpha = int(100 + 155 * self._glow_intensity)
        glow_color = QColor(base_color)
        glow_color.setAlpha(glow_alpha)

        # Draw outer glow (wider, more transparent)
        outer_glow = QColor(base_color)
        outer_glow.setAlpha(int(50 * self._glow_intensity))

        rect = self.rect()
        center_x = rect.width() // 2

        # Draw multiple glow layers for effect
        for i in range(3, 0, -1):
            glow_rect = QRect(
                center_x - i * 2,
                rect.top(),
                i * 4,
                rect.height()
            )
            layer_color = QColor(base_color)
            layer_color.setAlpha(int((30 + 20 * self._glow_intensity) / i))
            painter.fillRect(glow_rect, layer_color)

        # Draw main indicator line
        pen = QPen(glow_color)
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawLine(center_x, rect.top() + 2, center_x, rect.bottom() - 2)

        # Draw bright center
        bright_color = QColor(255, 255, 255, int(200 * self._glow_intensity))
        pen.setColor(bright_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(center_x, rect.top() + 2, center_x, rect.bottom() - 2)


class CommanderTabBar(QTabBar):
    """Custom tab bar with browser-like features.

    Features:
    - Drag tab out to detach into new window
    - Drop tab from other window to merge
    - Middle-click to close
    - Right-click context menu
    - New tab button
    """

    # Signals
    tab_detach_requested = Signal(int, QPoint)  # index, global position
    tab_drop_received = Signal(dict, int)  # tab data, insert index
    new_tab_requested = Signal()
    close_tab_requested = Signal(int)
    close_other_tabs_requested = Signal(int)
    close_tabs_to_right_requested = Signal(int)
    duplicate_tab_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Drag state
        self._drag_start_pos: QPoint | None = None
        self._drag_tab_index: int = -1
        self._is_dragging: bool = False

        # Drop indicator
        self._drop_indicator = DropIndicator(self)
        self._drop_insert_index = -1

        # Tab appearance
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setExpanding(False)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setDocumentMode(True)  # More native look on macOS
        self.setUsesScrollButtons(True)  # Show scroll buttons if many tabs

        # Apply styling
        self.setStyleSheet(TAB_STYLESHEET)

        # Accept drops
        self.setAcceptDrops(True)

        # Connect close button
        self.tabCloseRequested.connect(self._on_tab_close_requested)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def tabSizeHint(self, index: int) -> QSize:
        """Return custom tab size."""
        size = super().tabSizeHint(index)
        # Minimum width 120px, height 32px
        return QSize(max(size.width(), 120), max(size.height(), 32))

    def _on_tab_close_requested(self, index: int):
        """Handle tab close button click."""
        self.close_tab_requested.emit(index)

    # === Mouse Events for Drag Detection ===

    def mousePressEvent(self, event: QMouseEvent):
        """Track mouse press for potential drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self._drag_tab_index = self.tabAt(event.pos())
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Middle-click to close
            index = self.tabAt(event.pos())
            if index >= 0:
                self.close_tab_requested.emit(index)
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Detect drag out of tab bar for detach."""
        if not self._drag_start_pos:
            super().mouseMoveEvent(event)
            return

        if self._drag_tab_index < 0:
            super().mouseMoveEvent(event)
            return

        # Check if we're dragging far enough from start
        if not self._is_dragging:
            distance = (event.pos() - self._drag_start_pos).manhattanLength()
            if distance < QApplication.startDragDistance():
                super().mouseMoveEvent(event)
                return

        # Check if mouse is outside tab bar bounds (for detach)
        pos = event.pos()
        rect = self.rect()

        # Calculate distance outside the tab bar
        dist_outside = 0
        if pos.y() < rect.top():
            dist_outside = max(dist_outside, rect.top() - pos.y())
        elif pos.y() > rect.bottom():
            dist_outside = max(dist_outside, pos.y() - rect.bottom())

        if dist_outside > DETACH_THRESHOLD:
            # Start detach drag
            self._start_detach_drag(event)
            return

        # Normal tab reordering
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Reset drag state on release."""
        self._drag_start_pos = None
        self._drag_tab_index = -1
        self._is_dragging = False
        super().mouseReleaseEvent(event)

    # === Drag for Detach ===

    def _start_detach_drag(self, event: QMouseEvent):
        """Start a drag operation for tab detach/transfer."""
        if self._drag_tab_index < 0:
            return

        self._is_dragging = True

        # Create drag object
        drag = QDrag(self)

        # Create tab preview pixmap
        pixmap = self._create_tab_pixmap(self._drag_tab_index)
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))

        # Set mime data with tab info
        mime_data = QMimeData()

        # We'll serialize tab data in the parent window via signal
        # For now, just mark that this is a tab being dragged
        tab_info = {
            "source_window_id": id(self.window()),
            "tab_index": self._drag_tab_index,
            "tab_text": self.tabText(self._drag_tab_index),
            "tab_tooltip": self.tabToolTip(self._drag_tab_index),
        }
        mime_data.setData(TAB_MIME_TYPE, json.dumps(tab_info).encode())
        drag.setMimeData(mime_data)

        # Execute drag
        result = drag.exec(Qt.DropAction.MoveAction)

        # If drag was not accepted by another tab bar, emit detach signal
        if result == Qt.DropAction.IgnoreAction:
            # Detach to new window at cursor position
            global_pos = event.globalPosition().toPoint()
            self.tab_detach_requested.emit(self._drag_tab_index, global_pos)

        self._drag_start_pos = None
        self._drag_tab_index = -1
        self._is_dragging = False

    def _create_tab_pixmap(self, index: int) -> QPixmap:
        """Create a pixmap preview of the tab."""
        # Get tab rect
        rect = self.tabRect(index)

        # Create pixmap
        pixmap = QPixmap(rect.size())
        pixmap.fill(Qt.GlobalColor.transparent)

        # Render tab into pixmap
        painter = QPainter(pixmap)
        painter.setOpacity(0.8)

        # Draw tab background
        painter.fillRect(pixmap.rect(), self.palette().window())
        painter.setPen(self.palette().text().color())
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, self.tabText(index))

        painter.end()
        return pixmap

    # === Drop Events for Merge ===

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Accept tab drops from other windows."""
        if event.mimeData().hasFormat(TAB_MIME_TYPE):
            # Check if from different window
            data = event.mimeData().data(TAB_MIME_TYPE)
            tab_info = json.loads(bytes(data).decode())
            source_window_id = tab_info.get("source_window_id")

            if source_window_id != id(self.window()):
                # From different window - show drop indicator
                self._update_drop_indicator(event.position().toPoint())
                self._drop_indicator.start_animation()

            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """Track drop position and update indicator."""
        if event.mimeData().hasFormat(TAB_MIME_TYPE):
            # Check if from different window
            data = event.mimeData().data(TAB_MIME_TYPE)
            tab_info = json.loads(bytes(data).decode())
            source_window_id = tab_info.get("source_window_id")

            if source_window_id != id(self.window()):
                # Update indicator position
                self._update_drop_indicator(event.position().toPoint())

            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        """Hide drop indicator when drag leaves."""
        self._drop_indicator.stop_animation()
        self._drop_insert_index = -1
        super().dragLeaveEvent(event)

    def _update_drop_indicator(self, pos: QPoint):
        """Update the drop indicator position."""
        insert_index = self._get_insert_index(pos)
        self._drop_insert_index = insert_index

        # Calculate indicator position
        if self.count() == 0:
            # No tabs - show at left edge
            indicator_x = 2
        elif insert_index >= self.count():
            # After last tab
            last_rect = self.tabRect(self.count() - 1)
            indicator_x = last_rect.right() + 2
        else:
            # Before a tab
            tab_rect = self.tabRect(insert_index)
            indicator_x = tab_rect.left() - 2

        # Position the indicator
        self._drop_indicator.setGeometry(
            indicator_x - 6,  # Center the 12px wide indicator
            2,
            12,
            self.height() - 4
        )

        if not self._drop_indicator.isVisible():
            self._drop_indicator.start_animation()

    def dropEvent(self, event: QDropEvent):
        """Handle tab drop from other window."""
        # Hide drop indicator
        self._drop_indicator.stop_animation()
        self._drop_insert_index = -1

        if not event.mimeData().hasFormat(TAB_MIME_TYPE):
            super().dropEvent(event)
            return

        # Parse tab info
        data = event.mimeData().data(TAB_MIME_TYPE)
        tab_info = json.loads(bytes(data).decode())

        # Check if from same window (already handled by movable)
        source_window_id = tab_info.get("source_window_id")
        if source_window_id == id(self.window()):
            # Same window - let normal move handle it
            event.ignore()
            return

        # Calculate insert position
        pos = event.position().toPoint()
        insert_index = self._get_insert_index(pos)

        # Emit signal for parent to handle the actual data transfer
        # The parent window needs to request full tab data from source window
        self.tab_drop_received.emit(tab_info, insert_index)

        event.acceptProposedAction()

    def _get_insert_index(self, pos: QPoint) -> int:
        """Get tab index to insert at based on drop position."""
        for i in range(self.count()):
            rect = self.tabRect(i)
            if pos.x() < rect.center().x():
                return i
        return self.count()

    # === Context Menu ===

    def _show_context_menu(self, pos: QPoint):
        """Show tab context menu."""
        index = self.tabAt(pos)
        if index < 0:
            return

        menu = QMenu(self)

        # New Tab
        new_tab_action = menu.addAction("New Tab")
        new_tab_action.triggered.connect(self.new_tab_requested.emit)

        menu.addSeparator()

        # Duplicate Tab
        duplicate_action = menu.addAction("Duplicate Tab")
        duplicate_action.triggered.connect(lambda: self.duplicate_tab_requested.emit(index))

        menu.addSeparator()

        # Close Tab
        close_action = menu.addAction("Close Tab")
        close_action.triggered.connect(lambda: self.close_tab_requested.emit(index))

        # Close Other Tabs
        if self.count() > 1:
            close_others_action = menu.addAction("Close Other Tabs")
            close_others_action.triggered.connect(
                lambda: self.close_other_tabs_requested.emit(index)
            )

        # Close Tabs to the Right
        if index < self.count() - 1:
            close_right_action = menu.addAction("Close Tabs to the Right")
            close_right_action.triggered.connect(
                lambda: self.close_tabs_to_right_requested.emit(index)
            )

        menu.exec(self.mapToGlobal(pos))

    # === Tab Updates ===

    def update_tab(self, index: int, title: str, tooltip: str = None):
        """Update tab title and tooltip."""
        if 0 <= index < self.count():
            self.setTabText(index, title)
            if tooltip:
                self.setTabToolTip(index, tooltip)
