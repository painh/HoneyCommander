"""Application settings management."""

from pathlib import Path

from PySide6.QtCore import QSettings


class Settings:
    """Manage application settings using QSettings."""

    def __init__(self):
        self._settings = QSettings("Commander", "Commander")

    # Window geometry
    def save_window_geometry(self, geometry: bytes):
        """Save window geometry."""
        self._settings.setValue("window/geometry", geometry)

    def load_window_geometry(self) -> bytes | None:
        """Load window geometry."""
        return self._settings.value("window/geometry")

    def save_window_state(self, state: bytes):
        """Save window state."""
        self._settings.setValue("window/state", state)

    def load_window_state(self) -> bytes | None:
        """Load window state."""
        return self._settings.value("window/state")

    # Splitter sizes
    def save_splitter_sizes(self, sizes: list[int]):
        """Save splitter sizes."""
        self._settings.setValue("window/splitter_sizes", sizes)

    def load_splitter_sizes(self) -> list[int] | None:
        """Load splitter sizes."""
        sizes = self._settings.value("window/splitter_sizes")
        if sizes:
            return [int(s) for s in sizes]
        return None

    # Last path
    def save_last_path(self, path: Path):
        """Save last visited path."""
        self._settings.setValue("navigation/last_path", str(path))

    def load_last_path(self) -> Path | None:
        """Load last visited path."""
        path_str = self._settings.value("navigation/last_path")
        if path_str:
            path = Path(path_str)
            if path.exists():
                return path
        return None

    # View mode
    def save_view_mode(self, mode: str):
        """Save view mode."""
        self._settings.setValue("view/mode", mode)

    def load_view_mode(self) -> str:
        """Load view mode."""
        return self._settings.value("view/mode", "list")

    # Favorites
    def save_favorites(self, favorites: list[Path]):
        """Save favorite folders."""
        paths = [str(p) for p in favorites]
        self._settings.setValue("favorites/paths", paths)

    def load_favorites(self) -> list[Path]:
        """Load favorite folders."""
        paths = self._settings.value("favorites/paths")

        # First time: initialize with default favorites
        if paths is None:
            defaults = self._get_default_favorites()
            self.save_favorites(defaults)
            return defaults

        if paths:
            return [Path(p) for p in paths if Path(p).exists()]
        return []

    def _get_default_favorites(self) -> list[Path]:
        """Get default favorite folders."""
        import sys

        defaults = []

        home = Path.home()
        if home.exists():
            defaults.append(home)

        # Common folders
        common_folders = [
            home / "Downloads",
            home / "Documents",
            home / "Desktop",
        ]

        # macOS specific
        if sys.platform == "darwin":
            common_folders.append(Path("/Applications"))

        # Windows specific
        if sys.platform == "win32":
            common_folders.append(Path("C:/"))

        for folder in common_folders:
            if folder.exists():
                defaults.append(folder)

        return defaults

    def add_favorite(self, path: Path):
        """Add a folder to favorites."""
        favorites = self.load_favorites()
        if path not in favorites:
            favorites.append(path)
            self.save_favorites(favorites)

    def remove_favorite(self, path: Path):
        """Remove a folder from favorites."""
        favorites = self.load_favorites()
        if path in favorites:
            favorites.remove(path)
            self.save_favorites(favorites)

    def is_favorite(self, path: Path) -> bool:
        """Check if path is in favorites."""
        return path in self.load_favorites()

    # Preview panel visibility
    def save_preview_visible(self, visible: bool):
        """Save preview panel visibility."""
        self._settings.setValue("view/preview_visible", visible)

    def load_preview_visible(self) -> bool:
        """Load preview panel visibility."""
        return self._settings.value("view/preview_visible", True, type=bool)

    # Language
    def save_language(self, lang: str):
        """Save language setting."""
        self._settings.setValue("general/language", lang)

    def load_language(self) -> str | None:
        """Load language setting. Returns None if not set (use system default)."""
        return self._settings.value("general/language")

    # Fuzzy search timeout (in milliseconds)
    def save_fuzzy_search_timeout(self, timeout_ms: int):
        """Save fuzzy search timeout."""
        self._settings.setValue("search/fuzzy_timeout_ms", timeout_ms)

    def load_fuzzy_search_timeout(self) -> int:
        """Load fuzzy search timeout. Default 1500ms."""
        return self._settings.value("search/fuzzy_timeout_ms", 1500, type=int)

    # Thumbnail cache size
    def save_thumbnail_cache_size(self, size: int):
        """Save thumbnail cache size."""
        self._settings.setValue("performance/thumbnail_cache_size", size)

    def load_thumbnail_cache_size(self) -> int:
        """Load thumbnail cache size. Default 500."""
        return self._settings.value("performance/thumbnail_cache_size", 500, type=int)

    # Thumbnail size
    def save_thumbnail_size(self, size: int):
        """Save thumbnail size."""
        self._settings.setValue("view/thumbnail_size", size)

    def load_thumbnail_size(self) -> int:
        """Load thumbnail size. Default 128."""
        return self._settings.value("view/thumbnail_size", 128, type=int)

    # Undo stack size
    def save_undo_stack_size(self, size: int):
        """Save undo stack size."""
        self._settings.setValue("performance/undo_stack_size", size)

    def load_undo_stack_size(self) -> int:
        """Load undo stack size. Default 50."""
        return self._settings.value("performance/undo_stack_size", 50, type=int)

    # Animation frame thumbnail size
    def save_animation_thumb_size(self, size: int):
        """Save animation frame thumbnail size."""
        self._settings.setValue("view/animation_thumb_size", size)

    def load_animation_thumb_size(self) -> int:
        """Load animation frame thumbnail size. Default 70."""
        return self._settings.value("view/animation_thumb_size", 70, type=int)

    # Search max results
    def save_search_max_results(self, count: int):
        """Save search max results."""
        self._settings.setValue("search/max_results", count)

    def load_search_max_results(self) -> int:
        """Load search max results. Default 100."""
        return self._settings.value("search/max_results", 100, type=int)

    # Logging enabled
    def save_logging_enabled(self, enabled: bool):
        """Save logging enabled setting."""
        self._settings.setValue("debug/logging_enabled", enabled)

    def load_logging_enabled(self) -> bool:
        """Load logging enabled setting. Default True."""
        return self._settings.value("debug/logging_enabled", True, type=bool)

    # File type colors enabled (legacy, kept for compatibility)
    def save_file_type_colors_enabled(self, enabled: bool):
        """Save file type colors enabled setting."""
        self._settings.setValue("view/file_type_colors_enabled", enabled)

    def load_file_type_colors_enabled(self) -> bool:
        """Load file type colors enabled setting. Default True."""
        return self._settings.value("view/file_type_colors_enabled", True, type=bool)

    # Color theme
    def save_color_theme(self, theme_name: str):
        """Save color theme setting."""
        self._settings.setValue("view/color_theme", theme_name)

    def load_color_theme(self) -> str:
        """Load color theme setting. Default 'retro'."""
        return self._settings.value("view/color_theme", "retro", type=str)

    # Image viewer fullscreen mode
    def save_viewer_fullscreen(self, fullscreen: bool):
        """Save image viewer fullscreen mode preference."""
        self._settings.setValue("viewer/fullscreen", fullscreen)

    def load_viewer_fullscreen(self) -> bool:
        """Load image viewer fullscreen mode preference. Default True."""
        return self._settings.value("viewer/fullscreen", True, type=bool)

    # Image preload count (number of images to preload before/after current)
    def save_image_preload_count(self, count: int):
        """Save image preload count."""
        self._settings.setValue("viewer/preload_count", count)

    def load_image_preload_count(self) -> int:
        """Load image preload count. Default 3."""
        return self._settings.value("viewer/preload_count", 3, type=int)

    # Archive size threshold for extract prompt (in MB)
    def save_archive_size_threshold(self, size_mb: int):
        """Save archive size threshold for extract prompt."""
        self._settings.setValue("archive/size_threshold_mb", size_mb)

    def load_archive_size_threshold(self) -> int:
        """Load archive size threshold in MB. Default 100MB."""
        return self._settings.value("archive/size_threshold_mb", 100, type=int)
