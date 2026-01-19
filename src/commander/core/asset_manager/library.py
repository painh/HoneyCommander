"""Library and Asset management for Asset Manager."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .database import get_database


@dataclass
class Library:
    """Represents an asset library (a root folder for assets)."""

    id: int
    name: str
    root_path: Path
    scan_subdirs: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "Library":
        """Create Library from database row."""
        return cls(
            id=row["id"],
            name=row["name"],
            root_path=Path(row["root_path"]),
            scan_subdirs=bool(row["scan_subdirs"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass
class Asset:
    """Represents an asset file tracked in the library."""

    id: int
    library_id: int
    partial_hash: str
    file_size: int
    current_path: Optional[Path]
    original_filename: str
    file_extension: Optional[str]
    rating: int = 0
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    is_missing: bool = False
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row) -> "Asset":
        """Create Asset from database row."""
        return cls(
            id=row["id"],
            library_id=row["library_id"],
            partial_hash=row["partial_hash"],
            file_size=row["file_size"],
            current_path=Path(row["current_path"]) if row["current_path"] else None,
            original_filename=row["original_filename"],
            file_extension=row["file_extension"],
            rating=row["rating"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_seen_at=row["last_seen_at"],
            is_missing=bool(row["is_missing"]),
        )


class LibraryManager:
    """Manager for library CRUD operations."""

    _instance: Optional["LibraryManager"] = None

    def __new__(cls) -> "LibraryManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._db = get_database()
        self._initialized = True

    # === Library CRUD ===

    def create_library(self, name: str, root_path: Path, scan_subdirs: bool = True) -> Library:
        """Create a new library.

        Args:
            name: Library display name
            root_path: Root folder path
            scan_subdirs: Whether to scan subdirectories

        Returns:
            Created Library object

        Raises:
            ValueError: If name already exists or path is invalid
        """
        if not root_path.exists():
            raise ValueError(f"Path does not exist: {root_path}")
        if not root_path.is_dir():
            raise ValueError(f"Path is not a directory: {root_path}")

        self._db.execute(
            """
            INSERT INTO libraries (name, root_path, scan_subdirs)
            VALUES (?, ?, ?)
            """,
            (name, str(root_path), scan_subdirs),
        )
        self._db.commit()

        row = self._db.fetchone("SELECT * FROM libraries WHERE name = ?", (name,))
        return Library.from_row(row)

    def get_library(self, library_id: int) -> Optional[Library]:
        """Get library by ID."""
        row = self._db.fetchone("SELECT * FROM libraries WHERE id = ?", (library_id,))
        return Library.from_row(row) if row else None

    def get_library_by_name(self, name: str) -> Optional[Library]:
        """Get library by name."""
        row = self._db.fetchone("SELECT * FROM libraries WHERE name = ?", (name,))
        return Library.from_row(row) if row else None

    def get_all_libraries(self) -> list[Library]:
        """Get all libraries."""
        rows = self._db.fetchall("SELECT * FROM libraries ORDER BY name")
        return [Library.from_row(row) for row in rows]

    def update_library(self, library: Library) -> None:
        """Update library details."""
        self._db.execute(
            """
            UPDATE libraries
            SET name = ?, root_path = ?, scan_subdirs = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (library.name, str(library.root_path), library.scan_subdirs, library.id),
        )
        self._db.commit()

    def delete_library(self, library_id: int) -> None:
        """Delete library and all its assets."""
        self._db.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
        self._db.commit()

    def get_library_stats(self, library_id: int) -> dict:
        """Get statistics for a library."""
        asset_count = self._db.fetchone(
            "SELECT COUNT(*) as count FROM assets WHERE library_id = ?",
            (library_id,),
        )["count"]

        missing_count = self._db.fetchone(
            "SELECT COUNT(*) as count FROM assets WHERE library_id = ? AND is_missing = 1",
            (library_id,),
        )["count"]

        tagged_count = self._db.fetchone(
            """
            SELECT COUNT(DISTINCT a.id) as count
            FROM assets a
            JOIN asset_tags at ON a.id = at.asset_id
            WHERE a.library_id = ?
            """,
            (library_id,),
        )["count"]

        return {
            "total_assets": asset_count,
            "missing_assets": missing_count,
            "tagged_assets": tagged_count,
        }

    # === Asset CRUD ===

    def add_asset(
        self,
        library_id: int,
        partial_hash: str,
        file_size: int,
        current_path: Path,
        original_filename: Optional[str] = None,
    ) -> Asset:
        """Add a new asset to library.

        Args:
            library_id: Library ID
            partial_hash: Computed partial hash
            file_size: File size in bytes
            current_path: Current file path
            original_filename: Original filename (defaults to path filename)

        Returns:
            Created Asset object
        """
        if original_filename is None:
            original_filename = current_path.name

        file_extension = current_path.suffix.lower() if current_path.suffix else None

        self._db.execute(
            """
            INSERT INTO assets (
                library_id, partial_hash, file_size, current_path,
                original_filename, file_extension, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(library_id, partial_hash, file_size) DO UPDATE SET
                current_path = excluded.current_path,
                last_seen_at = CURRENT_TIMESTAMP,
                is_missing = FALSE
            """,
            (
                library_id,
                partial_hash,
                file_size,
                str(current_path),
                original_filename,
                file_extension,
            ),
        )
        self._db.commit()

        row = self._db.fetchone(
            """
            SELECT * FROM assets
            WHERE library_id = ? AND partial_hash = ? AND file_size = ?
            """,
            (library_id, partial_hash, file_size),
        )
        return Asset.from_row(row)

    def get_asset(self, asset_id: int) -> Optional[Asset]:
        """Get asset by ID."""
        row = self._db.fetchone("SELECT * FROM assets WHERE id = ?", (asset_id,))
        if row:
            asset = Asset.from_row(row)
            asset.tags = self._get_asset_tags(asset_id)
            return asset
        return None

    def get_asset_by_hash(
        self, library_id: int, partial_hash: str, file_size: int
    ) -> Optional[Asset]:
        """Get asset by hash and size."""
        row = self._db.fetchone(
            """
            SELECT * FROM assets
            WHERE library_id = ? AND partial_hash = ? AND file_size = ?
            """,
            (library_id, partial_hash, file_size),
        )
        if row:
            asset = Asset.from_row(row)
            asset.tags = self._get_asset_tags(asset.id)
            return asset
        return None

    def get_asset_by_path(self, path: Path) -> Optional[Asset]:
        """Get asset by current path."""
        row = self._db.fetchone("SELECT * FROM assets WHERE current_path = ?", (str(path),))
        if row:
            asset = Asset.from_row(row)
            asset.tags = self._get_asset_tags(asset.id)
            return asset
        return None

    def get_library_assets(
        self,
        library_id: int,
        tag_ids: Optional[list[int]] = None,
        rating_min: Optional[int] = None,
        include_missing: bool = False,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Asset]:
        """Get assets in library with optional filters.

        Args:
            library_id: Library ID
            tag_ids: Filter by tags (assets must have ALL specified tags)
            rating_min: Minimum rating filter
            include_missing: Whether to include missing files
            limit: Maximum number of results
            offset: Result offset for pagination

        Returns:
            List of matching assets
        """
        conditions = ["library_id = ?"]
        params: list = [library_id]

        if not include_missing:
            conditions.append("is_missing = 0")

        if rating_min is not None:
            conditions.append("rating >= ?")
            params.append(rating_min)

        # Tag filtering - assets must have ALL specified tags
        if tag_ids:
            conditions.append(
                f"""
                id IN (
                    SELECT asset_id FROM asset_tags
                    WHERE tag_id IN ({",".join("?" * len(tag_ids))})
                    GROUP BY asset_id
                    HAVING COUNT(DISTINCT tag_id) = ?
                )
                """
            )
            params.extend(tag_ids)
            params.append(len(tag_ids))

        sql = f"""
            SELECT * FROM assets
            WHERE {" AND ".join(conditions)}
            ORDER BY original_filename
        """

        if limit is not None:
            sql += f" LIMIT {limit} OFFSET {offset}"

        rows = self._db.fetchall(sql, tuple(params))
        assets = [Asset.from_row(row) for row in rows]

        # Load tags for each asset
        for asset in assets:
            asset.tags = self._get_asset_tags(asset.id)

        return assets

    def update_asset(
        self,
        asset_id: int,
        rating: Optional[int] = None,
        notes: Optional[str] = None,
        current_path: Optional[Path] = None,
        is_missing: Optional[bool] = None,
    ) -> None:
        """Update asset properties."""
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params = []

        if rating is not None:
            updates.append("rating = ?")
            params.append(rating)

        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if current_path is not None:
            updates.append("current_path = ?")
            params.append(str(current_path))

        if is_missing is not None:
            updates.append("is_missing = ?")
            params.append(is_missing)

        params.append(asset_id)

        self._db.execute(
            f"UPDATE assets SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        self._db.commit()

    def delete_asset(self, asset_id: int) -> None:
        """Delete an asset."""
        self._db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        self._db.commit()

    def mark_assets_missing(self, library_id: int) -> int:
        """Mark all assets in library as missing (for re-scan).

        Returns:
            Number of assets marked as missing
        """
        cursor = self._db.execute(
            "UPDATE assets SET is_missing = 1 WHERE library_id = ?",
            (library_id,),
        )
        self._db.commit()
        return cursor.rowcount

    def cleanup_missing_assets(self, library_id: int) -> int:
        """Delete all missing assets from library.

        Returns:
            Number of assets deleted
        """
        cursor = self._db.execute(
            "DELETE FROM assets WHERE library_id = ? AND is_missing = 1",
            (library_id,),
        )
        self._db.commit()
        return cursor.rowcount

    # === Asset Tags ===

    def _get_asset_tags(self, asset_id: int) -> list[str]:
        """Get tag names for an asset."""
        rows = self._db.fetchall(
            """
            SELECT t.namespace, t.name FROM tags t
            JOIN asset_tags at ON t.id = at.tag_id
            WHERE at.asset_id = ?
            ORDER BY t.namespace, t.name
            """,
            (asset_id,),
        )
        return [
            f"{row['namespace']}:{row['name']}" if row["namespace"] else row["name"] for row in rows
        ]

    def add_tag_to_asset(self, asset_id: int, tag_id: int) -> None:
        """Add a tag to an asset."""
        self._db.execute(
            """
            INSERT OR IGNORE INTO asset_tags (asset_id, tag_id)
            VALUES (?, ?)
            """,
            (asset_id, tag_id),
        )
        self._db.commit()

    def remove_tag_from_asset(self, asset_id: int, tag_id: int) -> None:
        """Remove a tag from an asset."""
        self._db.execute(
            "DELETE FROM asset_tags WHERE asset_id = ? AND tag_id = ?",
            (asset_id, tag_id),
        )
        self._db.commit()

    def get_asset_tag_ids(self, asset_id: int) -> list[int]:
        """Get tag IDs for an asset."""
        rows = self._db.fetchall(
            "SELECT tag_id FROM asset_tags WHERE asset_id = ?",
            (asset_id,),
        )
        return [row["tag_id"] for row in rows]


def get_library_manager() -> LibraryManager:
    """Get the singleton library manager instance."""
    return LibraryManager()
