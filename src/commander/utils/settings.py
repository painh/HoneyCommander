"""Application settings management."""

from pathlib import Path
from typing import Any

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
