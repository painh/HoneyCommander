"""Archive file handler (ZIP, RAR)."""

from abc import ABC, abstractmethod
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from dataclasses import dataclass

try:
    import rarfile

    HAS_RARFILE = True
except ImportError:
    HAS_RARFILE = False


@dataclass
class ArchiveEntry:
    """Entry in an archive file."""

    name: str
    path: str
    is_dir: bool
    size: int
    compressed_size: int
    modified_time: datetime | None


class ArchiveHandler(ABC):
    """Base class for archive handlers."""

    def __init__(self, archive_path: Path):
        self.archive_path = archive_path

    @abstractmethod
    def list_entries(self, internal_path: str = "") -> list[ArchiveEntry]:
        """List entries in archive at given internal path."""
        pass

    @abstractmethod
    def read_file(self, internal_path: str) -> bytes:
        """Read file content from archive."""
        pass

    @abstractmethod
    def extract(self, internal_path: str, destination: Path) -> None:
        """Extract file or folder to destination."""
        pass

    @abstractmethod
    def extract_all(self, destination: Path) -> None:
        """Extract entire archive to destination."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the archive."""
        pass


class ZipHandler(ArchiveHandler):
    """ZIP file handler."""

    def __init__(self, archive_path: Path):
        super().__init__(archive_path)
        self._zip = ZipFile(archive_path, "r")
        self._entries = self._build_entries()

    def _build_entries(self) -> dict[str, ArchiveEntry]:
        """Build entry dictionary from zip info."""
        entries = {}
        dirs_added = set()

        for info in self._zip.infolist():
            # Create entry
            path = info.filename.rstrip("/")
            name = Path(path).name
            is_dir = info.is_dir()

            try:
                mod_time = datetime(*info.date_time)
            except (ValueError, TypeError):
                mod_time = None

            entries[path] = ArchiveEntry(
                name=name,
                path=path,
                is_dir=is_dir,
                size=info.file_size,
                compressed_size=info.compress_size,
                modified_time=mod_time,
            )

            # Add parent directories
            parent = str(Path(path).parent)
            while parent and parent != "." and parent not in dirs_added:
                if parent not in entries:
                    entries[parent] = ArchiveEntry(
                        name=Path(parent).name,
                        path=parent,
                        is_dir=True,
                        size=0,
                        compressed_size=0,
                        modified_time=None,
                    )
                dirs_added.add(parent)
                parent = str(Path(parent).parent)

        return entries

    def list_entries(self, internal_path: str = "") -> list[ArchiveEntry]:
        """List entries at given path."""
        internal_path = internal_path.strip("/")
        result = []

        for path, entry in self._entries.items():
            # Check if entry is direct child of internal_path
            if internal_path:
                if not path.startswith(internal_path + "/"):
                    continue
                relative = path[len(internal_path) + 1 :]
            else:
                relative = path

            # Only direct children (no nested)
            if "/" not in relative and relative:
                result.append(entry)

        return sorted(result, key=lambda e: (not e.is_dir, e.name.lower()))

    def read_file(self, internal_path: str) -> bytes:
        """Read file content."""
        return self._zip.read(internal_path)

    def extract(self, internal_path: str, destination: Path) -> None:
        """Extract to destination."""
        self._zip.extract(internal_path, destination)

    def extract_all(self, destination: Path) -> None:
        """Extract entire archive to destination."""
        self._zip.extractall(destination)

    def close(self) -> None:
        """Close the archive."""
        self._zip.close()


class RarHandler(ArchiveHandler):
    """RAR file handler."""

    def __init__(self, archive_path: Path):
        super().__init__(archive_path)
        if not HAS_RARFILE:
            raise ImportError("rarfile module not available")
        self._rar = rarfile.RarFile(str(archive_path), "r")  # type: ignore[possibly-undefined]
        self._entries = self._build_entries()

    def _build_entries(self) -> dict[str, ArchiveEntry]:
        """Build entry dictionary."""
        entries = {}
        dirs_added = set()

        for info in self._rar.infolist():
            path = info.filename.rstrip("/\\")
            path = path.replace("\\", "/")
            name = Path(path).name
            is_dir = info.is_dir()

            try:
                mod_time = datetime(*info.date_time[:6]) if info.date_time else None
            except (ValueError, TypeError):
                mod_time = None

            entries[path] = ArchiveEntry(
                name=name,
                path=path,
                is_dir=is_dir,
                size=info.file_size,
                compressed_size=info.compress_size,
                modified_time=mod_time,
            )

            # Add parent directories
            parent = str(Path(path).parent)
            while parent and parent != "." and parent not in dirs_added:
                if parent not in entries:
                    entries[parent] = ArchiveEntry(
                        name=Path(parent).name,
                        path=parent,
                        is_dir=True,
                        size=0,
                        compressed_size=0,
                        modified_time=None,
                    )
                dirs_added.add(parent)
                parent = str(Path(parent).parent)

        return entries

    def list_entries(self, internal_path: str = "") -> list[ArchiveEntry]:
        """List entries at given path."""
        internal_path = internal_path.strip("/")
        result = []

        for path, entry in self._entries.items():
            if internal_path:
                if not path.startswith(internal_path + "/"):
                    continue
                relative = path[len(internal_path) + 1 :]
            else:
                relative = path

            if "/" not in relative and relative:
                result.append(entry)

        return sorted(result, key=lambda e: (not e.is_dir, e.name.lower()))

    def read_file(self, internal_path: str) -> bytes:
        """Read file content."""
        return self._rar.read(internal_path)

    def extract(self, internal_path: str, destination: Path) -> None:
        """Extract to destination."""
        self._rar.extract(internal_path, str(destination))

    def extract_all(self, destination: Path) -> None:
        """Extract entire archive to destination."""
        self._rar.extractall(str(destination))

    def close(self) -> None:
        """Close the archive."""
        self._rar.close()


class ArchiveManager:
    """Manager for handling different archive types."""

    HANDLERS: dict[str, type[ArchiveHandler]] = {
        ".zip": ZipHandler,
    }

    if HAS_RARFILE:
        HANDLERS[".rar"] = RarHandler

    # Split archive patterns (first volume only)
    SPLIT_RAR_PATTERNS = [".part1.rar", ".part01.rar", ".part001.rar"]

    @classmethod
    def is_archive(cls, path: Path) -> bool:
        """Check if path is a supported archive."""
        suffix = path.suffix.lower()
        if suffix in cls.HANDLERS:
            return True

        # Check for split RAR archives (only first volume)
        if HAS_RARFILE:
            name_lower = path.name.lower()
            for pattern in cls.SPLIT_RAR_PATTERNS:
                if name_lower.endswith(pattern):
                    return True

        return False

    @classmethod
    def is_split_archive_part(cls, path: Path) -> bool:
        """Check if path is a non-first part of a split archive (should be hidden)."""
        name_lower = path.name.lower()

        # RAR split parts: .part2.rar, .part02.rar, .r00, .r01, etc.
        if HAS_RARFILE:
            import re

            # .partN.rar where N > 1
            match = re.search(r"\.part(\d+)\.rar$", name_lower)
            if match and int(match.group(1)) > 1:
                return True

            # .r00, .r01, .r02, etc. (old style split)
            if re.search(r"\.r\d{2,}$", name_lower):
                return True

        return False

    @classmethod
    def get_handler(cls, archive_path: Path) -> ArchiveHandler | None:
        """Get appropriate handler for archive."""
        suffix = archive_path.suffix.lower()
        handler_class = cls.HANDLERS.get(suffix)

        if handler_class:
            try:
                return handler_class(archive_path)
            except Exception:
                return None

        # Check for split RAR archives
        if HAS_RARFILE:
            name_lower = archive_path.name.lower()
            for pattern in cls.SPLIT_RAR_PATTERNS:
                if name_lower.endswith(pattern):
                    try:
                        return RarHandler(archive_path)
                    except Exception:
                        return None

        return None

    @classmethod
    def supported_extensions(cls) -> list[str]:
        """Get list of supported extensions."""
        return list(cls.HANDLERS.keys())

    @classmethod
    def extract(cls, archive_path: Path, destination: Path) -> None:
        """Extract entire archive to destination."""
        handler = cls.get_handler(archive_path)
        if handler is None:
            raise ValueError(f"Unsupported archive format: {archive_path.suffix}")
        handler.extract_all(destination)
