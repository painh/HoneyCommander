"""Archive file handler (ZIP, RAR, 7z)."""

from abc import ABC, abstractmethod
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
from dataclasses import dataclass
import re

try:
    import rarfile

    HAS_RARFILE = True
except ImportError:
    HAS_RARFILE = False

try:
    import py7zr

    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False


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


class SevenZipHandler(ArchiveHandler):
    """7z file handler."""

    def __init__(self, archive_path: Path):
        super().__init__(archive_path)
        if not HAS_PY7ZR:
            raise ImportError("py7zr module not available")

        self._multivolume = None
        self._7z = self._open_archive(archive_path)
        self._entries = self._build_entries()
        # Cache for file contents (7z requires reading all at once)
        self._file_cache: dict[str, bytes] = {}

    def _open_archive(self, archive_path: Path):
        """Open archive, handling split volumes."""
        import multivolumefile

        # Check if this is a split archive (.7z.001 or .7z.0001)
        name_lower = archive_path.name.lower()
        if re.search(r"\.7z\.\d{3,}$", name_lower):
            # Remove the .NNN+ suffix to get base name for multivolumefile
            base_path = re.sub(r"\.\d{3,}$", "", str(archive_path))
            self._multivolume = multivolumefile.open(base_path, "rb")
            return py7zr.SevenZipFile(self._multivolume, "r")  # type: ignore[possibly-undefined]
        else:
            return py7zr.SevenZipFile(archive_path, "r")  # type: ignore[possibly-undefined]

    def _build_entries(self) -> dict[str, ArchiveEntry]:
        """Build entry dictionary."""
        entries = {}
        dirs_added = set()

        for info in self._7z.list():
            path = info.filename.rstrip("/\\")
            path = path.replace("\\", "/")
            name = Path(path).name
            is_dir = info.is_directory

            mod_time = info.creationtime if hasattr(info, "creationtime") else None

            entries[path] = ArchiveEntry(
                name=name,
                path=path,
                is_dir=is_dir,
                size=info.uncompressed if hasattr(info, "uncompressed") else 0,
                compressed_size=info.compressed if hasattr(info, "compressed") else 0,
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
        import tempfile

        # py7zr requires extracting to get content
        if internal_path in self._file_cache:
            return self._file_cache[internal_path]

        # Extract to temp directory and read
        self._7z.reset()
        with tempfile.TemporaryDirectory() as tmp:
            self._7z.extract(path=tmp, targets=[internal_path])
            extracted_path = Path(tmp) / internal_path
            if extracted_path.exists():
                data = extracted_path.read_bytes()
                self._file_cache[internal_path] = data
                return data
        return b""

    def extract(self, internal_path: str, destination: Path) -> None:
        """Extract to destination."""
        self._7z.reset()
        self._7z.extract(destination, [internal_path])

    def extract_all(self, destination: Path) -> None:
        """Extract entire archive to destination."""
        self._7z.reset()
        self._7z.extractall(destination)

    def close(self) -> None:
        """Close the archive."""
        self._7z.close()
        if self._multivolume:
            self._multivolume.close()
        self._file_cache.clear()


class ArchiveManager:
    """Manager for handling different archive types."""

    HANDLERS: dict[str, type[ArchiveHandler]] = {
        ".zip": ZipHandler,
    }

    if HAS_RARFILE:
        HANDLERS[".rar"] = RarHandler

    if HAS_PY7ZR:
        HANDLERS[".7z"] = SevenZipHandler

    # Split archive patterns (first volume only)
    SPLIT_RAR_PATTERNS = [".part1.rar", ".part01.rar", ".part001.rar"]
    SPLIT_7Z_PATTERN = re.compile(r"\.7z\.0*1$", re.IGNORECASE)  # .7z.001 or .7z.0001

    @classmethod
    def is_archive(cls, path: Path) -> bool:
        """Check if path is a supported archive."""
        suffix = path.suffix.lower()
        if suffix in cls.HANDLERS:
            return True

        name_lower = path.name.lower()

        # Check for split RAR archives (only first volume)
        if HAS_RARFILE:
            for pattern in cls.SPLIT_RAR_PATTERNS:
                if name_lower.endswith(pattern):
                    return True

        # Check for split 7z archives (only first volume .7z.001)
        if HAS_PY7ZR:
            if cls.SPLIT_7Z_PATTERN.search(name_lower):
                return True

        return False

    @classmethod
    def is_split_archive_part(cls, path: Path) -> bool:
        """Check if path is a non-first part of a split archive (should be hidden)."""
        name_lower = path.name.lower()

        # RAR split parts: .part2.rar, .part02.rar, .r00, .r01, etc.
        if HAS_RARFILE:
            # .partN.rar where N > 1
            match = re.search(r"\.part(\d+)\.rar$", name_lower)
            if match and int(match.group(1)) > 1:
                return True

            # .r00, .r01, .r02, etc. (old style split)
            if re.search(r"\.r\d{2,}$", name_lower):
                return True

        # 7z split parts: .7z.002, .7z.003, .7z.0002, etc.
        if HAS_PY7ZR:
            match = re.search(r"\.7z\.(\d{3,})$", name_lower)
            if match and int(match.group(1)) > 1:
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

        name_lower = archive_path.name.lower()

        # Check for split RAR archives
        if HAS_RARFILE:
            for pattern in cls.SPLIT_RAR_PATTERNS:
                if name_lower.endswith(pattern):
                    try:
                        return RarHandler(archive_path)
                    except Exception:
                        return None

        # Check for split 7z archives
        if HAS_PY7ZR:
            if cls.SPLIT_7Z_PATTERN.search(name_lower):
                try:
                    return SevenZipHandler(archive_path)
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

    @classmethod
    def smart_extract(cls, archive_path: Path, base_destination: Path) -> Path:
        """Extract archive smartly based on contents.

        If archive has a single top-level folder, extract directly to base_destination.
        Otherwise, create a folder named after the archive and extract there.

        Returns the actual extraction directory.
        """
        handler = cls.get_handler(archive_path)
        if handler is None:
            raise ValueError(f"Unsupported archive format: {archive_path.suffix}")

        # Get top-level entries
        entries = handler.list_entries()
        top_level_dirs = [e for e in entries if e.is_dir and "/" not in e.name.rstrip("/")]
        top_level_files = [e for e in entries if not e.is_dir and "/" not in e.name]

        # Check if there's exactly one top-level folder and no top-level files
        if len(top_level_dirs) == 1 and len(top_level_files) == 0:
            # Single top-level folder - extract directly
            extract_dir = base_destination
        else:
            # Multiple items or files at top level - create wrapper folder
            # Get proper stem for split archives
            stem = cls._get_archive_stem(archive_path)
            extract_dir = base_destination / stem

        extract_dir.mkdir(parents=True, exist_ok=True)
        handler.extract_all(extract_dir)
        handler.close()
        return extract_dir

    @classmethod
    def _get_archive_stem(cls, archive_path: Path) -> str:
        """Get the stem name for an archive, handling split archives."""
        stem = archive_path.stem
        name_lower = archive_path.name.lower()

        # Handle split 7z: file.7z.001 -> file
        if re.search(r"\.7z\.\d{3,}$", name_lower):
            stem = archive_path.stem  # "file.7z"
            if stem.lower().endswith(".7z"):
                stem = stem[:-3]  # "file"
        # Handle split RAR: file.part1.rar -> file
        elif re.search(r"\.part\d+\.rar$", name_lower):
            stem = re.sub(r"\.part\d+$", "", archive_path.stem, flags=re.IGNORECASE)

        return stem
