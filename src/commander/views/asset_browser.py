"""Asset browser view for displaying library assets."""

from typing import Optional, List

from PySide6.QtCore import Qt, Signal, QSize, QModelIndex
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListView,
    QTableView,
    QStackedWidget,
    QLineEdit,
    QComboBox,
    QLabel,
    QMenu,
    QAbstractItemView,
    QHeaderView,
)

from ..models.asset_model import AssetTableModel, AssetFilterProxyModel
from ..core.asset_manager import Asset, get_library_manager, get_tag_manager
from ..views.asset_thumbnail_delegate import AssetThumbnailDelegate


class AssetBrowserView(QWidget):
    """Browser view for displaying and interacting with library assets.

    Signals:
        asset_selected: Emitted when an asset is selected (asset_id)
        asset_activated: Emitted when an asset is double-clicked (asset_id)
        selection_changed: Emitted when selection changes (list of asset_ids)
    """

    asset_selected = Signal(int)
    asset_activated = Signal(int)
    selection_changed = Signal(list)

    # View modes
    VIEW_LIST = "list"
    VIEW_GRID = "grid"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._library_id: Optional[int] = None
        self._current_view_mode = self.VIEW_GRID
        self._tag_filter: List[int] = []
        self._setup_ui()
        self._setup_models()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 4, 4, 0)

        # Search
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search assets...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self._search_edit, 1)

        # View mode toggle
        self._view_mode_combo = QComboBox()
        self._view_mode_combo.addItem("Grid", self.VIEW_GRID)
        self._view_mode_combo.addItem("List", self.VIEW_LIST)
        self._view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        toolbar.addWidget(self._view_mode_combo)

        layout.addLayout(toolbar)

        # Stacked widget for views
        self._stack = QStackedWidget()

        # Grid view (icon view)
        self._grid_view = QListView()
        self._grid_view.setViewMode(QListView.ViewMode.IconMode)
        self._grid_view.setResizeMode(QListView.ResizeMode.Adjust)
        self._grid_view.setSpacing(8)
        self._grid_view.setIconSize(QSize(128, 128))
        self._grid_view.setGridSize(QSize(150, 170))
        self._grid_view.setUniformItemSizes(True)
        self._grid_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._grid_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._grid_view.customContextMenuRequested.connect(self._show_context_menu)
        self._grid_view.doubleClicked.connect(self._on_item_activated)

        # Setup thumbnail delegate for lazy loading
        self._thumbnail_delegate = AssetThumbnailDelegate(self._grid_view)
        self._thumbnail_delegate.set_thumbnail_size(QSize(128, 128))
        self._thumbnail_delegate.set_item_size(QSize(150, 170))
        self._grid_view.setItemDelegate(self._thumbnail_delegate)

        self._stack.addWidget(self._grid_view)

        # List view (table)
        self._list_view = QTableView()
        self._list_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list_view.setAlternatingRowColors(True)
        self._list_view.setSortingEnabled(True)
        self._list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_view.customContextMenuRequested.connect(self._show_context_menu)
        self._list_view.doubleClicked.connect(self._on_item_activated)

        # Configure header
        header = self._list_view.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self._stack.addWidget(self._list_view)

        layout.addWidget(self._stack)

        # Status bar
        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: gray; padding: 4px;")
        layout.addWidget(self._status_label)

        # Set initial view mode
        self._stack.setCurrentIndex(0)  # Grid view

    def _setup_models(self) -> None:
        """Setup data models."""
        self._model = AssetTableModel(self)
        self._proxy_model = AssetFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)

        # Set model on views
        self._grid_view.setModel(self._proxy_model)
        self._grid_view.setModelColumn(0)  # Name column

        self._list_view.setModel(self._proxy_model)

        # Connect selection changes
        self._grid_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._list_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def set_library(self, library_id: Optional[int]) -> None:
        """Set the library to display."""
        self._library_id = library_id
        self._tag_filter = []
        self._model.set_library(library_id)
        self._update_status()

    def set_tag_filter(self, tag_ids: List[int]) -> None:
        """Set tag filter."""
        self._tag_filter = tag_ids
        self._model.reload(tag_ids=tag_ids if tag_ids else None)
        self._update_status()

    def reload(self) -> None:
        """Reload assets."""
        self._model.reload(tag_ids=self._tag_filter if self._tag_filter else None)
        self._update_status()

    def _on_search_changed(self, text: str) -> None:
        """Handle search text change."""
        self._proxy_model.set_search_text(text)
        self._update_status()

    def _on_view_mode_changed(self, index: int) -> None:
        """Handle view mode change."""
        mode = self._view_mode_combo.itemData(index)
        self._current_view_mode = mode

        if mode == self.VIEW_GRID:
            self._stack.setCurrentWidget(self._grid_view)
        else:
            self._stack.setCurrentWidget(self._list_view)

    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        asset_ids = self._get_selected_asset_ids()

        if len(asset_ids) == 1:
            self.asset_selected.emit(asset_ids[0])

        self.selection_changed.emit(asset_ids)

    def _on_item_activated(self, index: QModelIndex) -> None:
        """Handle item double-click."""
        source_index = self._proxy_model.mapToSource(index)
        asset = self._model.get_asset(source_index.row())
        if asset:
            self.asset_activated.emit(asset.id)

    def _get_selected_asset_ids(self) -> List[int]:
        """Get list of selected asset IDs."""
        current_view = (
            self._grid_view if self._current_view_mode == self.VIEW_GRID else self._list_view
        )

        selection = current_view.selectionModel().selectedIndexes()
        asset_ids = set()

        for index in selection:
            source_index = self._proxy_model.mapToSource(index)
            asset = self._model.get_asset(source_index.row())
            if asset:
                asset_ids.add(asset.id)

        return list(asset_ids)

    def _show_context_menu(self, pos) -> None:
        """Show context menu for assets."""
        current_view = (
            self._grid_view if self._current_view_mode == self.VIEW_GRID else self._list_view
        )

        index = current_view.indexAt(pos)
        if not index.isValid():
            return

        source_index = self._proxy_model.mapToSource(index)
        asset = self._model.get_asset(source_index.row())
        if not asset:
            return

        menu = QMenu(self)

        # Open action
        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self._open_asset(asset))

        # Open folder action
        if asset.current_path:
            folder_action = menu.addAction("Open Folder")
            folder_action.triggered.connect(lambda: self._open_folder(asset))

        menu.addSeparator()

        # Tag submenu
        tag_menu = menu.addMenu("Add Tag")
        self._populate_tag_menu(tag_menu, asset)

        # Remove tag submenu
        if asset.tags:
            remove_tag_menu = menu.addMenu("Remove Tag")
            for tag_str in asset.tags:
                action = remove_tag_menu.addAction(tag_str)
                action.triggered.connect(lambda checked, t=tag_str: self._remove_tag(asset, t))

        menu.addSeparator()

        # Rating submenu
        rating_menu = menu.addMenu("Rating")
        for i in range(6):
            stars = "★" * i if i > 0 else "No Rating"
            action = rating_menu.addAction(stars)
            action.triggered.connect(lambda checked, r=i: self._set_rating(asset, r))
            if asset.rating == i:
                action.setCheckable(True)
                action.setChecked(True)

        menu.exec(current_view.mapToGlobal(pos))

    def _populate_tag_menu(self, menu: QMenu, asset: Asset) -> None:
        """Populate tag menu with available tags."""
        if self._library_id is None:
            return

        tag_manager = get_tag_manager()
        tags = tag_manager.get_library_tags(self._library_id)

        # Filter out already-applied tags
        existing_tags = set(asset.tags)

        for tag in tags[:20]:  # Limit to 20 tags
            if tag.full_name not in existing_tags:
                action = menu.addAction(tag.full_name)
                action.triggered.connect(lambda checked, t=tag: self._add_tag(asset, t))

        if not tags:
            menu.addAction("(No tags available)").setEnabled(False)

    def _open_asset(self, asset: Asset) -> None:
        """Open asset file."""
        if asset.current_path and asset.current_path.exists():
            import subprocess
            import sys

            if sys.platform == "darwin":
                subprocess.run(["open", str(asset.current_path)])
            elif sys.platform == "win32":
                subprocess.run(["start", "", str(asset.current_path)], shell=True)
            else:
                subprocess.run(["xdg-open", str(asset.current_path)])

    def _open_folder(self, asset: Asset) -> None:
        """Open containing folder."""
        if asset.current_path and asset.current_path.exists():
            import subprocess
            import sys

            folder = asset.current_path.parent
            if sys.platform == "darwin":
                subprocess.run(["open", str(folder)])
            elif sys.platform == "win32":
                subprocess.run(["explorer", str(folder)])
            else:
                subprocess.run(["xdg-open", str(folder)])

    def _add_tag(self, asset: Asset, tag) -> None:
        """Add tag to asset."""
        lib_manager = get_library_manager()
        lib_manager.add_tag_to_asset(asset.id, tag.id)
        self._model.update_asset(asset.id)

    def _remove_tag(self, asset: Asset, tag_str: str) -> None:
        """Remove tag from asset."""
        tag_manager = get_tag_manager()
        namespace, name = tag_manager.parse_tag_string(tag_str)
        tag = tag_manager.get_tag_by_name(name, namespace)

        if tag:
            lib_manager = get_library_manager()
            lib_manager.remove_tag_from_asset(asset.id, tag.id)
            self._model.update_asset(asset.id)

    def _set_rating(self, asset: Asset, rating: int) -> None:
        """Set asset rating."""
        lib_manager = get_library_manager()
        lib_manager.update_asset(asset.id, rating=rating)
        self._model.update_asset(asset.id)

    def _update_status(self) -> None:
        """Update status bar."""
        total = self._model.rowCount()
        filtered = self._proxy_model.rowCount()

        if total == filtered:
            self._status_label.setText(f"{total} assets")
        else:
            self._status_label.setText(f"{filtered} of {total} assets")

    def get_selected_assets(self) -> List[Asset]:
        """Get list of selected assets."""
        asset_ids = self._get_selected_asset_ids()
        assets = []
        for aid in asset_ids:
            asset = self._model.get_asset_by_id(aid)
            if asset:
                assets.append(asset)
        return assets

    def select_asset(self, asset_id: int) -> None:
        """Select an asset by ID."""
        row = self._model.get_row_by_id(asset_id)
        if row < 0:
            return

        source_index = self._model.index(row, 0)
        proxy_index = self._proxy_model.mapFromSource(source_index)

        current_view = (
            self._grid_view if self._current_view_mode == self.VIEW_GRID else self._list_view
        )
        current_view.setCurrentIndex(proxy_index)
        current_view.scrollTo(proxy_index)
