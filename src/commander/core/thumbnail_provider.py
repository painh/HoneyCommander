"""Thumbnail provider with caching."""

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSize, QObject
from PySide6.QtGui import QPixmap

from commander.core.image_loader import load_pixmap, ALL_IMAGE_FORMATS
from commander.utils.settings import Settings


class ThumbnailWorker(QThread):
    """Background worker for generating thumbnails."""

    thumbnail_ready = Signal(str, QPixmap)  # path_str, pixmap

    def __init__(self, path: Path, size: QSize):
        super().__init__()
        self._path = path
        self._size = size

    def run(self):
        """Generate thumbnail."""
        try:
            pixmap = load_pixmap(self._path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.thumbnail_ready.emit(str(self._path), scaled)
        except Exception:
            pass


class ThumbnailProvider(QObject):
    """Provides thumbnails with in-memory caching.

    Features:
    - LRU cache with configurable size
    - Concurrent loading limit to prevent resource exhaustion
    - Only loads visible items (when used with delegate)
    """

    SUPPORTED_FORMATS = ALL_IMAGE_FORMATS
    MAX_CONCURRENT_LOADS = 6  # Limit concurrent thumbnail loading

    thumbnail_ready = Signal(str)  # path_str - emitted when thumbnail is ready

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = Settings()
        self._cache: dict[str, QPixmap] = {}
        self._pending: dict[str, ThumbnailWorker] = {}
        self._queue: list[Path] = []  # Paths waiting to be loaded
        self._max_cache_size = self._settings.load_thumbnail_cache_size()
        size = self._settings.load_thumbnail_size()
        self._thumbnail_size = QSize(size, size)

    def set_thumbnail_size(self, size: QSize):
        """Set thumbnail size and clear cache if size changed."""
        if size != self._thumbnail_size:
            self._thumbnail_size = size
            self._cache.clear()

    def get_thumbnail(self, path: Path) -> QPixmap | None:
        """Get thumbnail for path. Returns None if not cached yet."""
        path_str = str(path)

        # Check cache
        if path_str in self._cache:
            return self._cache[path_str]

        # Check if supported format
        if path.suffix.lower() not in self.SUPPORTED_FORMATS:
            return None

        # Check if already loading
        if path_str in self._pending:
            return None

        # Start loading
        self._load_thumbnail(path)
        return None

    def _load_thumbnail(self, path: Path):
        """Queue thumbnail for loading."""
        path_str = str(path)

        # Add to queue if not already there
        if path not in self._queue and path_str not in self._pending:
            self._queue.append(path)

        # Process queue
        self._process_queue()

    def _process_queue(self):
        """Process queued thumbnails up to concurrent limit."""
        while self._queue and len(self._pending) < self.MAX_CONCURRENT_LOADS:
            path = self._queue.pop(0)
            path_str = str(path)

            # Skip if already in cache (loaded while queued)
            if path_str in self._cache:
                continue

            # Skip if already loading
            if path_str in self._pending:
                continue

            # Start loading
            worker = ThumbnailWorker(path, self._thumbnail_size)
            worker.thumbnail_ready.connect(self._on_thumbnail_ready)
            worker.finished.connect(lambda p=path_str: self._on_worker_finished(p))

            self._pending[path_str] = worker
            worker.start()

    def _on_thumbnail_ready(self, path_str: str, pixmap: QPixmap):
        """Handle thumbnail ready."""
        # Manage cache size
        if len(self._cache) >= self._max_cache_size:
            # Remove oldest entries (first 100)
            keys_to_remove = list(self._cache.keys())[:100]
            for key in keys_to_remove:
                del self._cache[key]

        self._cache[path_str] = pixmap
        self.thumbnail_ready.emit(path_str)

    def _on_worker_finished(self, path_str: str):
        """Clean up finished worker and process queue."""
        if path_str in self._pending:
            worker = self._pending.pop(path_str)
            worker.deleteLater()

        # Process more from queue
        self._process_queue()

    def clear_cache(self):
        """Clear thumbnail cache."""
        self._cache.clear()

    def is_supported(self, path: Path) -> bool:
        """Check if path is a supported image format."""
        return path.suffix.lower() in self.SUPPORTED_FORMATS


# Global instance
_provider: ThumbnailProvider | None = None


def get_thumbnail_provider() -> ThumbnailProvider:
    """Get the global thumbnail provider instance."""
    global _provider
    if _provider is None:
        _provider = ThumbnailProvider()
    return _provider
