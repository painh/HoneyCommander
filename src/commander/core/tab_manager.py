"""Tab manager - coordinates tabs within a single window."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QStackedWidget

from commander.widgets.tab_content import TabContentWidget


class TabManager(QObject):
    """Manages tabs within a single MainWindow.

    Coordinates tab creation, deletion, switching, and state management.
    """

    # Signals
    tab_added = Signal(int)  # index
    tab_removed = Signal(int)  # index
    current_tab_changed = Signal(int, TabContentWidget)  # index, content
    tab_title_changed = Signal(int, str)  # index, title
    all_tabs_closed = Signal()  # Emitted when last tab is closed

    def __init__(self, stack_widget: QStackedWidget, parent=None):
        super().__init__(parent)
        self._stack = stack_widget
        self._tabs: list[TabContentWidget] = []
        self._current_index: int = -1

        # Recently closed tabs for reopen feature
        self._closed_tabs: list[dict] = []
        self._max_closed_tabs: int = 10

    # === Tab CRUD ===

    def create_tab(
        self,
        path: Path = None,
        activate: bool = True,
        index: int = -1,
    ) -> int:
        """Create a new tab.

        Args:
            path: Initial path for the tab. Defaults to home directory.
            activate: Whether to activate the new tab.
            index: Position to insert at. -1 means append.

        Returns:
            Index of the new tab.
        """
        tab = TabContentWidget(path or Path.home())

        # Connect tab signals
        tab.path_changed.connect(lambda p, t=tab: self._on_tab_path_changed(t, p))

        # Insert at position
        if index < 0 or index >= len(self._tabs):
            index = len(self._tabs)
            self._tabs.append(tab)
            self._stack.addWidget(tab)
        else:
            self._tabs.insert(index, tab)
            self._stack.insertWidget(index, tab)

        self.tab_added.emit(index)

        if activate or len(self._tabs) == 1:
            self.switch_to_tab(index)

        return index

    def close_tab(self, index: int) -> bool:
        """Close tab at index.

        Args:
            index: Tab index to close.

        Returns:
            True if tab was closed, False if it was the last tab.
        """
        if index < 0 or index >= len(self._tabs):
            return False

        tab = self._tabs[index]

        # Save to closed tabs before removing
        self._remember_closed_tab(tab.serialize())

        # Clean up tab
        tab.cleanup()

        # Remove from list and stack
        self._tabs.pop(index)
        self._stack.removeWidget(tab)
        tab.deleteLater()

        self.tab_removed.emit(index)

        # Handle current index
        if len(self._tabs) == 0:
            self._current_index = -1
            self.all_tabs_closed.emit()
            return True

        # Adjust current index if needed
        if self._current_index >= len(self._tabs):
            self._current_index = len(self._tabs) - 1
        elif self._current_index > index:
            self._current_index -= 1

        # Emit current tab changed
        if self._current_index >= 0:
            self.current_tab_changed.emit(self._current_index, self._tabs[self._current_index])

        return True

    def close_other_tabs(self, keep_index: int):
        """Close all tabs except the one at keep_index."""
        # Close tabs after the kept one first (to avoid index shifting issues)
        for i in range(len(self._tabs) - 1, keep_index, -1):
            self.close_tab(i)

        # Then close tabs before
        for i in range(keep_index - 1, -1, -1):
            self.close_tab(i)

    def close_tabs_to_right(self, index: int):
        """Close all tabs to the right of index."""
        for i in range(len(self._tabs) - 1, index, -1):
            self.close_tab(i)

    def duplicate_tab(self, index: int) -> int:
        """Duplicate tab at index.

        Returns:
            Index of the new duplicated tab.
        """
        if index < 0 or index >= len(self._tabs):
            return -1

        source_tab = self._tabs[index]
        data = source_tab.serialize()

        # Create new tab next to source
        new_index = self.create_tab(path=source_tab.current_path, activate=True, index=index + 1)

        # Restore full state
        new_tab = self._tabs[new_index]
        new_tab.deserialize(data)

        return new_index

    # === Tab Navigation ===

    def switch_to_tab(self, index: int):
        """Switch to tab at index."""
        if index < 0 or index >= len(self._tabs):
            return

        self._current_index = index
        self._stack.setCurrentIndex(index)

        tab = self._tabs[index]
        self.current_tab_changed.emit(index, tab)

    def next_tab(self):
        """Switch to next tab (wraps around)."""
        if len(self._tabs) <= 1:
            return
        next_index = (self._current_index + 1) % len(self._tabs)
        self.switch_to_tab(next_index)

    def prev_tab(self):
        """Switch to previous tab (wraps around)."""
        if len(self._tabs) <= 1:
            return
        prev_index = (self._current_index - 1) % len(self._tabs)
        self.switch_to_tab(prev_index)

    def switch_to_tab_number(self, number: int):
        """Switch to tab by number (1-9). 9 goes to last tab."""
        if number == 9:
            self.switch_to_tab(len(self._tabs) - 1)
        elif 1 <= number <= len(self._tabs):
            self.switch_to_tab(number - 1)

    # === Tab Reordering ===

    def move_tab(self, from_index: int, to_index: int):
        """Move tab from one position to another."""
        if from_index == to_index:
            return
        if from_index < 0 or from_index >= len(self._tabs):
            return
        if to_index < 0 or to_index >= len(self._tabs):
            return

        tab = self._tabs.pop(from_index)
        self._tabs.insert(to_index, tab)

        # Update current index
        if self._current_index == from_index:
            self._current_index = to_index
        elif from_index < self._current_index <= to_index:
            self._current_index -= 1
        elif to_index <= self._current_index < from_index:
            self._current_index += 1

    # === Tab State ===

    def get_tab(self, index: int) -> Optional[TabContentWidget]:
        """Get tab content at index."""
        if 0 <= index < len(self._tabs):
            return self._tabs[index]
        return None

    def get_current_tab(self) -> Optional[TabContentWidget]:
        """Get currently active tab."""
        if 0 <= self._current_index < len(self._tabs):
            return self._tabs[self._current_index]
        return None

    @property
    def current_index(self) -> int:
        """Get current tab index."""
        return self._current_index

    def count(self) -> int:
        """Get number of tabs."""
        return len(self._tabs)

    def get_all_tabs(self) -> list[TabContentWidget]:
        """Get all tab contents."""
        return list(self._tabs)

    # === Tab Detach/Merge ===

    def detach_tab(self, index: int) -> Optional[dict]:
        """Remove tab and return its serialized state for transfer.

        Returns:
            Serialized tab data, or None if invalid index.
        """
        if index < 0 or index >= len(self._tabs):
            return None

        tab = self._tabs[index]
        data = tab.serialize()

        # Don't remember as "closed" since it's being transferred
        tab.cleanup()
        self._tabs.pop(index)
        self._stack.removeWidget(tab)
        tab.deleteLater()

        self.tab_removed.emit(index)

        # Handle current index
        if len(self._tabs) == 0:
            self._current_index = -1
            self.all_tabs_closed.emit()
        else:
            if self._current_index >= len(self._tabs):
                self._current_index = len(self._tabs) - 1
            elif self._current_index > index:
                self._current_index -= 1

            self.current_tab_changed.emit(self._current_index, self._tabs[self._current_index])

        return data

    def merge_tab(self, tab_data: dict, index: int = -1) -> int:
        """Add tab from serialized data (received from another window).

        Args:
            tab_data: Serialized tab state.
            index: Position to insert. -1 means append.

        Returns:
            Index of the new tab.
        """
        path_str = tab_data.get("path", str(Path.home()))
        path = Path(path_str)
        if not path.exists():
            path = Path.home()

        new_index = self.create_tab(path, activate=True, index=index)
        new_tab = self._tabs[new_index]
        new_tab.deserialize(tab_data)

        return new_index

    # === Closed Tabs ===

    def _remember_closed_tab(self, tab_data: dict):
        """Remember closed tab for reopen feature."""
        self._closed_tabs.append(tab_data)
        if len(self._closed_tabs) > self._max_closed_tabs:
            self._closed_tabs.pop(0)

    def reopen_closed_tab(self) -> int:
        """Reopen most recently closed tab.

        Returns:
            Index of reopened tab, or -1 if no tabs to reopen.
        """
        if not self._closed_tabs:
            return -1

        tab_data = self._closed_tabs.pop()
        return self.merge_tab(tab_data)

    def has_closed_tabs(self) -> bool:
        """Check if there are closed tabs that can be reopened."""
        return len(self._closed_tabs) > 0

    # === Internal ===

    def _on_tab_path_changed(self, tab: TabContentWidget, path: Path):
        """Handle tab path change."""
        try:
            index = self._tabs.index(tab)
            self.tab_title_changed.emit(index, tab.get_tab_title())
        except ValueError:
            pass

    # === Serialization ===

    def serialize_all(self) -> list[dict]:
        """Serialize all tabs for session persistence."""
        return [tab.serialize() for tab in self._tabs]

    def get_active_tab_index(self) -> int:
        """Get index of active tab for session persistence."""
        return self._current_index
