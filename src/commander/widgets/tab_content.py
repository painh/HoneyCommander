"""Tab content widget - contains all per-tab state and UI."""

from pathlib import Path

from PySide6.QtCore import Signal, QFileSystemWatcher
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QSplitter,
)
from PySide6.QtCore import Qt

from commander.views.folder_tree import FolderTreeView
from commander.views.file_list import FileListView
from commander.views.preview_panel import PreviewPanel
from commander.widgets.address_bar import AddressBar
from commander.widgets.favorites_panel import FavoritesPanel
from commander.views.network_panel import NetworkDrivePanel


class TabContentWidget(QWidget):
    """Container for all per-tab UI and state.

    Each tab has its own:
    - AddressBar
    - FolderTreeView
    - FileListView
    - PreviewPanel
    - Navigation history
    """

    # Signals
    path_changed = Signal(Path)
    item_selected = Signal(Path)
    item_activated = Signal(Path)
    request_new_tab = Signal(Path)
    request_new_window = Signal(Path)
    files_dropped = Signal(list, Path)
    favorite_toggled = Signal(Path, bool)

    def __init__(self, initial_path: Path = None, parent=None):
        super().__init__(parent)

        # Navigation state
        self._current_path: Path = initial_path or Path.home()
        self._history: list[Path] = []
        self._history_index: int = -1

        # File system watcher
        self._watcher = QFileSystemWatcher()
        self._watcher.directoryChanged.connect(self._on_directory_changed)

        self._setup_ui()
        self._connect_signals()

        # Navigate to initial path
        if initial_path and initial_path.exists():
            self.navigate_to(initial_path)
        else:
            self.navigate_to(Path.home())

    def _setup_ui(self):
        """Setup the tab's UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Address bar (per-tab)
        self._address_bar = AddressBar()
        layout.addWidget(self._address_bar)

        # 3-panel splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._network_panel = NetworkDrivePanel()
        self._favorites_panel = FavoritesPanel()
        self._folder_tree = FolderTreeView()

        left_layout.addWidget(self._network_panel)
        left_layout.addWidget(self._favorites_panel)
        left_layout.addWidget(self._folder_tree, stretch=1)

        # Center panel - file list
        self._file_list = FileListView()

        # Right panel - preview
        self._preview_panel = PreviewPanel()

        self._splitter.addWidget(left_panel)
        self._splitter.addWidget(self._file_list)
        self._splitter.addWidget(self._preview_panel)

        # Default sizes (1:3:1 ratio)
        self._splitter.setSizes([200, 600, 200])

        layout.addWidget(self._splitter, stretch=1)

    def _connect_signals(self):
        """Connect internal signals."""
        # Address bar
        self._address_bar.path_changed.connect(self.navigate_to)
        self._address_bar.favorite_toggled.connect(self._on_favorite_toggled)

        # Folder tree
        self._folder_tree.folder_selected.connect(self.navigate_to)
        self._folder_tree.files_dropped.connect(self._on_files_dropped)
        self._folder_tree.request_new_window.connect(self.request_new_window.emit)

        # Favorites
        self._favorites_panel.folder_selected.connect(self.navigate_to)

        # File list
        self._file_list.item_activated.connect(self._on_item_activated)
        self._file_list.item_selected.connect(self._on_item_selected)
        self._file_list.request_new_window.connect(self.request_new_window.emit)

    def _on_favorite_toggled(self, path: Path, is_favorite: bool):
        """Handle favorite toggle."""
        self._favorites_panel.refresh()
        self.favorite_toggled.emit(path, is_favorite)

    def _on_files_dropped(self, paths: list[Path], destination: Path):
        """Forward file drop event."""
        self.files_dropped.emit(paths, destination)

    def _on_item_activated(self, path: Path):
        """Handle file list item activation."""
        if path.is_dir():
            self.navigate_to(path)
        else:
            self.item_activated.emit(path)

    def _on_item_selected(self, path: Path):
        """Handle file list item selection."""
        self._preview_panel.show_preview(path)
        self.item_selected.emit(path)

    def _on_directory_changed(self, path: str):
        """Handle external directory changes."""
        if Path(path) == self._current_path:
            self.refresh()

    # === Navigation Methods ===

    def navigate_to(self, path: Path):
        """Navigate to a directory."""
        if not path.exists() or not path.is_dir():
            return

        # Update watcher
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        self._watcher.addPath(str(path))

        self._current_path = path
        self._address_bar.set_path(path)
        self._file_list.set_root_path(path)
        self._folder_tree.select_path(path)

        # Update history
        if self._history_index < len(self._history) - 1:
            self._history = self._history[: self._history_index + 1]
        if not self._history or self._history[-1] != path:
            self._history.append(path)
            self._history_index = len(self._history) - 1

        self.path_changed.emit(path)

    def go_back(self) -> bool:
        """Navigate back in history. Returns True if navigated."""
        if self._history_index > 0:
            self._history_index -= 1
            path = self._history[self._history_index]
            self._navigate_without_history(path)
            return True
        return False

    def go_forward(self) -> bool:
        """Navigate forward in history. Returns True if navigated."""
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            path = self._history[self._history_index]
            self._navigate_without_history(path)
            return True
        return False

    def go_up(self) -> bool:
        """Navigate to parent directory. Returns True if navigated."""
        # Check if file list has search text to clear
        if self._file_list.handle_backspace():
            return True

        parent = self._current_path.parent
        if parent != self._current_path:
            self.navigate_to(parent)
            return True
        return False

    def _navigate_without_history(self, path: Path):
        """Navigate without modifying history (for back/forward)."""
        if not path.exists() or not path.is_dir():
            return

        # Update watcher
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
        self._watcher.addPath(str(path))

        self._current_path = path
        self._address_bar.set_path(path)
        self._file_list.set_root_path(path)
        self._folder_tree.select_path(path)

        self.path_changed.emit(path)

    def refresh(self):
        """Refresh current view."""
        self._file_list.set_root_path(self._current_path)

    # === State Access ===

    @property
    def current_path(self) -> Path:
        """Get current path."""
        return self._current_path

    @property
    def can_go_back(self) -> bool:
        """Check if back navigation is possible."""
        return self._history_index > 0

    @property
    def can_go_forward(self) -> bool:
        """Check if forward navigation is possible."""
        return self._history_index < len(self._history) - 1

    @property
    def can_go_up(self) -> bool:
        """Check if up navigation is possible."""
        return self._current_path.parent != self._current_path

    def get_tab_title(self) -> str:
        """Get title for tab (folder name)."""
        return self._current_path.name or str(self._current_path)

    def get_tab_tooltip(self) -> str:
        """Get tooltip for tab (full path)."""
        return str(self._current_path)

    # === Component Access ===

    @property
    def file_list(self) -> FileListView:
        """Access file list view."""
        return self._file_list

    @property
    def folder_tree(self) -> FolderTreeView:
        """Access folder tree view."""
        return self._folder_tree

    @property
    def preview_panel(self) -> PreviewPanel:
        """Access preview panel."""
        return self._preview_panel

    @property
    def address_bar(self) -> AddressBar:
        """Access address bar."""
        return self._address_bar

    @property
    def splitter(self) -> QSplitter:
        """Access splitter for saving/restoring sizes."""
        return self._splitter

    def get_selected_paths(self) -> list[Path]:
        """Get selected paths from file list."""
        return self._file_list.get_selected_paths()

    def get_view_mode(self) -> str:
        """Get current view mode."""
        return self._file_list.get_view_mode()

    def set_view_mode(self, mode: str):
        """Set view mode."""
        self._file_list.set_view_mode(mode)

    # === Serialization ===

    def serialize(self) -> dict:
        """Serialize tab state for persistence or tab transfer."""
        return {
            "path": str(self._current_path),
            "history": [str(p) for p in self._history],
            "history_index": self._history_index,
            "view_mode": self.get_view_mode(),
            "splitter_sizes": self._splitter.sizes(),
        }

    def deserialize(self, data: dict):
        """Restore tab state from serialized data."""
        # Restore history
        self._history = [Path(p) for p in data.get("history", [])]
        self._history_index = data.get("history_index", -1)

        # Restore view mode
        view_mode = data.get("view_mode", "list")
        self.set_view_mode(view_mode)

        # Restore splitter sizes (with minimum size protection)
        sizes = data.get("splitter_sizes")
        if sizes and len(sizes) >= 3:
            # Ensure minimum sizes to prevent invisible panels
            min_left = 100
            min_center = 200
            min_right = 100
            sizes = [
                max(sizes[0], min_left),
                max(sizes[1], min_center),
                max(sizes[2], min_right),
            ]
            self._splitter.setSizes(sizes)

        # Navigate to path (do this last)
        path_str = data.get("path")
        if path_str:
            path = Path(path_str)
            if path.exists():
                self._navigate_without_history(path)

    def cleanup(self):
        """Clean up resources."""
        self._network_panel.cleanup()
        if self._watcher.directories():
            self._watcher.removePaths(self._watcher.directories())
