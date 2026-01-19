"""File list view - center panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QDir, QModelIndex, QSize, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListView,
    QAbstractItemView,
    QStackedWidget,
    QHeaderView,
    QLabel,
)

from commander.views.file_list.drop_views import DropEnabledTreeView, DropEnabledListView
from commander.views.file_list.thumbnail_delegate import ThumbnailDelegate
from commander.views.file_list.file_list_models import ColoredFileSystemModel, ViewMode
from commander.views.file_list.file_list_context_menu import FileListContextMenuMixin
from commander.views.file_list.file_list_operations import FileListOperationsMixin
from commander.views.file_list.file_list_search import FileListSearchMixin
from commander.utils.settings import Settings


class FileListView(FileListSearchMixin, FileListOperationsMixin, FileListContextMenuMixin, QWidget):
    """Center panel file list view with multiple view modes."""

    item_selected = Signal(Path)
    item_activated = Signal(Path)
    request_compress = Signal(list)
    request_terminal = Signal(Path)
    request_new_window = Signal(Path)  # Request to open folder in new window

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._model = ColoredFileSystemModel()
        self._model.setFilter(
            QDir.Filter.AllEntries
            | QDir.Filter.NoDotAndDotDot
            | QDir.Filter.Hidden
            | QDir.Filter.System
        )

        self._view_mode = ViewMode.LIST
        self._current_path: Path | None = None

        # Fuzzy search
        self._settings = Settings()
        self._search_text = ""
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(self._settings.load_fuzzy_search_timeout())
        self._search_timer.timeout.connect(self._clear_search)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the stacked widget with different views."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Set focus policy for the container
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        # Tree view for list mode (with columns)
        self._tree_view = DropEnabledTreeView()
        self._tree_view.setModel(self._model)
        self._tree_view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._tree_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree_view.setDragEnabled(True)
        self._tree_view.setDropIndicatorShown(True)
        self._tree_view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._tree_view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree_view.customContextMenuRequested.connect(self._show_context_menu)
        self._tree_view.clicked.connect(self._on_clicked)
        self._tree_view.doubleClicked.connect(self._on_double_clicked)
        self._tree_view.setRootIsDecorated(False)  # Don't show expand arrows
        self._tree_view.setSortingEnabled(True)
        self._tree_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._tree_view.files_dropped.connect(self._on_files_dropped)

        # Configure header
        header = self._tree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Size
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Date

        self._stack.addWidget(self._tree_view)

        # List view for icons/thumbnails mode
        self._list_view = DropEnabledListView()
        self._list_view.setModel(self._model)
        self._list_view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list_view.setDragEnabled(True)
        self._list_view.setDropIndicatorShown(True)
        self._list_view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._list_view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_view.customContextMenuRequested.connect(self._show_context_menu)
        self._list_view.clicked.connect(self._on_clicked)
        self._list_view.doubleClicked.connect(self._on_double_clicked)
        self._list_view.files_dropped.connect(self._on_files_dropped)

        # Thumbnail delegate
        self._thumbnail_delegate = ThumbnailDelegate(self._list_view)
        self._default_delegate = self._list_view.itemDelegate()

        self._stack.addWidget(self._list_view)

        # Default: list mode (tree view)
        self._stack.setCurrentWidget(self._tree_view)

        # Search overlay (hidden by default)
        self._search_label = QLabel(self)
        self._search_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 120, 212, 0.9);
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        self._search_label.hide()
        self._search_label.raise_()  # Ensure it's on top

        # Install event filter to capture key events from views
        self._tree_view.installEventFilter(self)
        self._list_view.installEventFilter(self)

    def _current_view(self) -> QAbstractItemView:
        """Get the current active view."""
        widget = self._stack.currentWidget()
        # Both DropEnabledTreeView and DropEnabledListView are QAbstractItemView subclasses
        assert isinstance(widget, QAbstractItemView)
        return widget

    def focusInEvent(self, event) -> None:
        """Forward focus to the current view."""
        super().focusInEvent(event)
        self._current_view().setFocus()
        self._update_focus_style()

    def focusOutEvent(self, event) -> None:
        """Handle focus out."""
        super().focusOutEvent(event)
        self._update_focus_style()

    def _update_focus_style(self) -> None:
        """Update border style based on focus and theme."""
        from commander.utils.themes import get_theme_manager

        theme = get_theme_manager().get_current_theme()

        # Check if any child view has focus
        has_focus = self.hasFocus() or self._tree_view.hasFocus() or self._list_view.hasFocus()

        # Only apply focus border for retro theme
        # Use dark cyan/teal like classic MDIR style
        if theme.name == "retro" and has_focus:
            self.setStyleSheet("FileListView { border: 2px solid #008080; }")
        else:
            self.setStyleSheet("")

    def set_root_path(self, path: Path) -> None:
        """Set the directory to display."""
        self._current_path = path
        self._model.setRootPath(str(path))

        root_index = self._model.index(str(path))
        self._tree_view.setRootIndex(root_index)
        self._list_view.setRootIndex(root_index)

        # Update drop target path
        self._tree_view.set_current_path(path)
        self._list_view.set_current_path(path)

        # Reconnect selection changed signals
        self._connect_selection_signals()

    def _connect_selection_signals(self) -> None:
        """Connect selection changed signals for both views."""
        # Tree view - disconnect then reconnect
        tree_selection_model = self._tree_view.selectionModel()
        try:
            tree_selection_model.selectionChanged.disconnect(self._on_selection_changed)
        except (RuntimeError, TypeError):
            pass
        tree_selection_model.selectionChanged.connect(self._on_selection_changed)

        # List view - disconnect then reconnect
        list_selection_model = self._list_view.selectionModel()
        try:
            list_selection_model.selectionChanged.disconnect(self._on_selection_changed)
        except (RuntimeError, TypeError):
            pass
        list_selection_model.selectionChanged.connect(self._on_selection_changed)

    def get_view_mode(self) -> str:
        """Get current view mode."""
        return self._view_mode.value

    def set_view_mode(self, mode: str) -> None:
        """Change view mode (list, icons, thumbnails)."""
        self._view_mode = ViewMode(mode)

        if self._view_mode == ViewMode.LIST:
            # Use tree view for detailed list with columns
            self._stack.setCurrentWidget(self._tree_view)
            self._tree_view.setIconSize(QSize(16, 16))
        elif self._view_mode == ViewMode.ICONS:
            # Use list view in icon mode
            self._stack.setCurrentWidget(self._list_view)
            self._list_view.setViewMode(QListView.ViewMode.IconMode)
            self._list_view.setGridSize(QSize(100, 80))
            self._list_view.setIconSize(QSize(48, 48))
            self._list_view.setSpacing(10)
            self._list_view.setWordWrap(True)
            self._list_view.setItemDelegate(self._default_delegate)
        elif self._view_mode == ViewMode.THUMBNAILS:
            # Use list view in thumbnail mode
            self._stack.setCurrentWidget(self._list_view)
            self._list_view.setViewMode(QListView.ViewMode.IconMode)
            self._list_view.setGridSize(QSize(150, 150))
            self._list_view.setIconSize(QSize(128, 128))
            self._list_view.setSpacing(10)
            self._list_view.setWordWrap(True)
            self._list_view.setItemDelegate(self._thumbnail_delegate)

    def _on_clicked(self, index: QModelIndex) -> None:
        """Handle single click - select and preview."""
        path = Path(self._model.filePath(index))
        self.item_selected.emit(path)

    def _on_selection_changed(self, selected, deselected) -> None:
        """Handle selection change (keyboard navigation)."""
        view = self._current_view()
        indexes = view.selectionModel().selectedIndexes()
        if indexes:
            # Get the first column index (name)
            for idx in indexes:
                if idx.column() == 0:
                    path = Path(self._model.filePath(idx))
                    self.item_selected.emit(path)
                    break

    def _on_double_clicked(self, index: QModelIndex) -> None:
        """Handle double click - activate (open/navigate)."""
        path = Path(self._model.filePath(index))
        self.item_activated.emit(path)

    def get_selected_paths(self) -> list[Path]:
        """Get list of selected file paths."""
        paths: list[Path] = []
        view = self._current_view()
        for index in view.selectionModel().selectedIndexes():
            if index.column() == 0:  # Only count name column
                path = Path(self._model.filePath(index))
                if path not in paths:
                    paths.append(path)
        return paths

    def start_rename(self) -> None:
        """Start renaming selected item."""
        view = self._current_view()
        indexes = view.selectionModel().selectedIndexes()
        for idx in indexes:
            if idx.column() == 0:
                view.edit(idx)
                break

    def selectionModel(self):
        """Get selection model of current view (for compatibility)."""
        return self._current_view().selectionModel()

    def selectedIndexes(self):
        """Get selected indexes of current view (for compatibility)."""
        return self._current_view().selectionModel().selectedIndexes()

    def _select_paths(self, paths: list[Path]) -> None:
        """Select specific paths in the current view."""
        from PySide6.QtCore import QItemSelectionModel

        view = self._current_view()
        selection_model = view.selectionModel()
        selection_model.clear()

        for path in paths:
            index = self._model.index(str(path))
            if index.isValid():
                selection_model.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
