"""Background library scanning for Asset Manager."""

from pathlib import Path
from typing import Optional, Set

from PySide6.QtCore import QThread, Signal

from .hasher import compute_partial_hash
from .library import Library, get_library_manager


# Common asset file extensions
ASSET_EXTENSIONS = {
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tga",
    ".tiff",
    ".tif",
    ".webp",
    ".ico",
    ".svg",
    ".psd",
    ".xcf",
    ".kra",
    ".clip",
    # 3D
    ".fbx",
    ".obj",
    ".gltf",
    ".glb",
    ".blend",
    ".max",
    ".ma",
    ".mb",
    ".3ds",
    ".dae",
    ".stl",
    ".ply",
    # Audio
    ".wav",
    ".mp3",
    ".ogg",
    ".flac",
    ".aac",
    ".m4a",
    ".wma",
    # Video
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".wmv",
    # Fonts
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    # Documents
    ".pdf",
    ".txt",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    # Game-specific
    ".atlas",
    ".spine",
    ".prefab",
    ".asset",
    ".mat",
    ".shader",
}


class LibraryScanner(QThread):
    """Background thread for scanning library files.

    Signals:
        progress: Emits (current, total, current_file) during scan
        file_scanned: Emits (asset_id, path) for each scanned file
        finished_scan: Emits (added_count, updated_count, missing_count)
        error: Emits error message string
    """

    progress = Signal(int, int, str)
    file_scanned = Signal(int, str)
    finished_scan = Signal(int, int, int)
    error = Signal(str)

    def __init__(
        self,
        library_id: int,
        incremental: bool = True,
        extensions: Optional[Set[str]] = None,
        parent=None,
    ):
        """Initialize scanner.

        Args:
            library_id: ID of library to scan
            incremental: If True, only scan new/changed files. If False, full rescan.
            extensions: Set of file extensions to scan. None = use defaults.
            parent: Parent QObject
        """
        super().__init__(parent)
        self._library_id = library_id
        self._incremental = incremental
        self._extensions = extensions or ASSET_EXTENSIONS
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the scan."""
        self._cancelled = True

    def run(self) -> None:
        """Execute the scan in background thread."""
        try:
            self._do_scan()
        except Exception as e:
            self.error.emit(str(e))

    def _do_scan(self) -> None:
        """Perform the actual scanning."""
        lib_manager = get_library_manager()
        library = lib_manager.get_library(self._library_id)

        if library is None:
            self.error.emit(f"Library not found: {self._library_id}")
            return

        if not library.root_path.exists():
            self.error.emit(f"Library path does not exist: {library.root_path}")
            return

        # Collect all files to scan
        files_to_scan = self._collect_files(library)

        if self._cancelled:
            return

        total = len(files_to_scan)
        added = 0
        updated = 0

        # If not incremental, mark all existing assets as missing first
        if not self._incremental:
            lib_manager.mark_assets_missing(self._library_id)

        # Scan each file
        for i, file_path in enumerate(files_to_scan):
            if self._cancelled:
                break

            self.progress.emit(i + 1, total, str(file_path.name))

            result = self._scan_file(file_path, library)
            if result:
                asset_id, is_new = result
                if is_new:
                    added += 1
                else:
                    updated += 1
                self.file_scanned.emit(asset_id, str(file_path))

        # Count missing assets
        stats = lib_manager.get_library_stats(self._library_id)
        missing = stats["missing_assets"]

        self.finished_scan.emit(added, updated, missing)

    def _collect_files(self, library: Library) -> list[Path]:
        """Collect all files to scan in the library."""
        files = []
        root = library.root_path

        if library.scan_subdirs:
            iterator = root.rglob("*")
        else:
            iterator = root.glob("*")

        for path in iterator:
            if self._cancelled:
                break

            if not path.is_file():
                continue

            # Check extension
            ext = path.suffix.lower()
            if ext not in self._extensions:
                continue

            # Skip hidden files
            if path.name.startswith("."):
                continue

            files.append(path)

        return files

    def _scan_file(self, path: Path, library: Library) -> Optional[tuple[int, bool]]:
        """Scan a single file.

        Returns:
            Tuple of (asset_id, is_new) or None if failed
        """
        try:
            # Compute partial hash
            hash_result = compute_partial_hash(path)
            if hash_result is None:
                return None

            partial_hash, file_size = hash_result

            lib_manager = get_library_manager()

            # Check if asset exists
            existing = lib_manager.get_asset_by_hash(library.id, partial_hash, file_size)

            if existing:
                # Update path if changed
                if existing.current_path != path:
                    lib_manager.update_asset(
                        existing.id,
                        current_path=path,
                        is_missing=False,
                    )
                else:
                    # Just mark as not missing
                    lib_manager.update_asset(existing.id, is_missing=False)
                return existing.id, False
            else:
                # Add new asset
                asset = lib_manager.add_asset(
                    library.id,
                    partial_hash,
                    file_size,
                    path,
                )
                return asset.id, True

        except (OSError, IOError):
            return None


class AssetVerifier(QThread):
    """Background thread for verifying asset file existence.

    Checks if all tracked assets still exist at their current paths.

    Signals:
        progress: Emits (current, total)
        asset_missing: Emits asset_id for each missing asset
        asset_found: Emits (asset_id, new_path) for relocated assets
        finished_verify: Emits (verified_count, missing_count, relocated_count)
    """

    progress = Signal(int, int)
    asset_missing = Signal(int)
    asset_found = Signal(int, str)
    finished_verify = Signal(int, int, int)

    def __init__(self, library_id: int, relocate: bool = False, parent=None):
        """Initialize verifier.

        Args:
            library_id: ID of library to verify
            relocate: If True, try to find moved files by hash
            parent: Parent QObject
        """
        super().__init__(parent)
        self._library_id = library_id
        self._relocate = relocate
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled = True

    def run(self) -> None:
        """Execute verification in background thread."""
        lib_manager = get_library_manager()
        library = lib_manager.get_library(self._library_id)

        if library is None:
            return

        assets = lib_manager.get_library_assets(self._library_id, include_missing=True)
        total = len(assets)

        verified = 0
        missing = 0
        relocated = 0

        for i, asset in enumerate(assets):
            if self._cancelled:
                break

            self.progress.emit(i + 1, total)

            if asset.current_path and asset.current_path.exists():
                # Verify hash still matches
                try:
                    actual_hash, actual_size = compute_partial_hash(asset.current_path)
                    if actual_hash == asset.partial_hash and actual_size == asset.file_size:
                        verified += 1
                        if asset.is_missing:
                            lib_manager.update_asset(asset.id, is_missing=False)
                        continue
                except (OSError, IOError):
                    pass

            # File not found or hash mismatch
            if self._relocate:
                # Try to find the file by hash
                from .hasher import find_file_by_hash

                new_path = find_file_by_hash(
                    library.root_path,
                    asset.partial_hash,
                    asset.file_size,
                    recursive=library.scan_subdirs,
                )

                if new_path:
                    lib_manager.update_asset(
                        asset.id,
                        current_path=new_path,
                        is_missing=False,
                    )
                    relocated += 1
                    self.asset_found.emit(asset.id, str(new_path))
                    continue

            # Mark as missing
            lib_manager.update_asset(asset.id, is_missing=True)
            missing += 1
            self.asset_missing.emit(asset.id)

        self.finished_verify.emit(verified, missing, relocated)


def scan_library_sync(
    library_id: int,
    incremental: bool = True,
    extensions: Optional[Set[str]] = None,
    progress_callback=None,
) -> tuple[int, int, int]:
    """Synchronous library scan (for testing or CLI use).

    Args:
        library_id: Library to scan
        incremental: Incremental or full scan
        extensions: File extensions to scan
        progress_callback: Optional callback(current, total, filename)

    Returns:
        Tuple of (added, updated, missing) counts
    """
    lib_manager = get_library_manager()
    library = lib_manager.get_library(library_id)

    if library is None:
        raise ValueError(f"Library not found: {library_id}")

    if not library.root_path.exists():
        raise ValueError(f"Library path does not exist: {library.root_path}")

    extensions = extensions or ASSET_EXTENSIONS

    # Collect files
    files = []
    iterator = library.root_path.rglob("*") if library.scan_subdirs else library.root_path.glob("*")

    for path in iterator:
        if path.is_file() and path.suffix.lower() in extensions:
            if not path.name.startswith("."):
                files.append(path)

    total = len(files)
    added = 0
    updated = 0

    if not incremental:
        lib_manager.mark_assets_missing(library_id)

    for i, path in enumerate(files):
        if progress_callback:
            progress_callback(i + 1, total, path.name)

        try:
            partial_hash, file_size = compute_partial_hash(path)
            existing = lib_manager.get_asset_by_hash(library_id, partial_hash, file_size)

            if existing:
                lib_manager.update_asset(existing.id, current_path=path, is_missing=False)
                updated += 1
            else:
                lib_manager.add_asset(library_id, partial_hash, file_size, path)
                added += 1
        except (OSError, IOError):
            continue

    stats = lib_manager.get_library_stats(library_id)
    return added, updated, stats["missing_assets"]
