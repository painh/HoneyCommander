"""Image caching utilities for the viewer."""

from __future__ import annotations

from pathlib import Path
from io import BytesIO
from dataclasses import dataclass
from collections import OrderedDict
from threading import Thread

from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QPixmap

from commander.core.image_loader import load_pixmap


@dataclass
class ArchiveImageEntry:
    """Represents an image inside an archive."""

    archive_path: Path  # Path to the archive file
    internal_path: str  # Path inside the archive
    name: str  # Display name


def load_pixmap_from_bytes(data: bytes) -> QPixmap:
    """Load QPixmap from raw bytes."""
    from PIL import Image

    try:
        # Try loading with PIL first (supports more formats)
        pil_image = Image.open(BytesIO(data))
        if pil_image.mode not in ("RGB", "RGBA"):
            pil_image = pil_image.convert("RGBA")

        # Convert PIL to QPixmap
        from PySide6.QtGui import QImage

        if pil_image.mode == "RGBA":
            qformat = QImage.Format.Format_RGBA8888
        else:
            qformat = QImage.Format.Format_RGB888

        img_data = pil_image.tobytes()
        qimage = QImage(img_data, pil_image.width, pil_image.height, qformat)
        return QPixmap.fromImage(qimage)
    except Exception:
        # Fallback to Qt's loader
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        return pixmap


class ImageCache(QObject):
    """LRU cache for preloading images around the current index."""

    image_loaded = Signal(object, QPixmap)  # path, pixmap

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cache: OrderedDict[Path, QPixmap] = OrderedDict()
        self._max_size: int = 10  # Will be updated from settings
        self._loading: set[Path] = set()

    def set_max_size(self, size: int) -> None:
        """Set max cache size (preload_count * 2 + 1 for current)."""
        self._max_size = max(1, size)
        self._evict_if_needed()

    def get(self, path: Path) -> QPixmap | None:
        """Get cached pixmap, returns None if not cached."""
        if path in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(path)
            return self._cache[path]
        return None

    def put(self, path: Path, pixmap: QPixmap) -> None:
        """Put pixmap in cache."""
        if path in self._cache:
            self._cache.move_to_end(path)
        else:
            self._cache[path] = pixmap
            self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache exceeds max size."""
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def is_cached(self, path: Path) -> bool:
        """Check if path is in cache."""
        return path in self._cache

    def is_loading(self, path: Path) -> bool:
        """Check if path is currently being loaded."""
        return path in self._loading

    def preload(self, path: Path) -> None:
        """Preload image in background thread."""
        if path in self._cache or path in self._loading:
            return

        self._loading.add(path)

        def load_task():
            try:
                pixmap = load_pixmap(path)
                if pixmap and not pixmap.isNull():
                    self.image_loaded.emit(path, pixmap)
            finally:
                self._loading.discard(path)

        thread = Thread(target=load_task, daemon=True)
        thread.start()

    def get_cached_paths(self) -> list[Path]:
        """Get list of all cached paths (in order, oldest first)."""
        return list(self._cache.keys())

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._loading.clear()
