"""SQLite database connection and migrations for Asset Manager."""

import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QStandardPaths


# Schema version for migrations
SCHEMA_VERSION = 1

# SQL schema definition
SCHEMA_SQL = """
-- Libraries table
CREATE TABLE IF NOT EXISTS libraries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    root_path TEXT NOT NULL,
    scan_subdirs BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Assets table (files tracked by partial hash)
CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_id INTEGER NOT NULL,
    partial_hash TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    current_path TEXT,
    original_filename TEXT NOT NULL,
    file_extension TEXT,
    rating INTEGER DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP,
    is_missing BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (library_id) REFERENCES libraries(id) ON DELETE CASCADE,
    UNIQUE(library_id, partial_hash, file_size)
);

-- Tags table
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    namespace TEXT DEFAULT '',
    color TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(namespace, name)
);

-- Asset-Tag junction table
CREATE TABLE IF NOT EXISTS asset_tags (
    asset_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, tag_id),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Tag relationships (siblings and parents)
CREATE TABLE IF NOT EXISTS tag_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_id INTEGER NOT NULL,
    related_tag_id INTEGER NOT NULL,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN ('sibling', 'parent')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
    FOREIGN KEY (related_tag_id) REFERENCES tags(id) ON DELETE CASCADE,
    UNIQUE(tag_id, related_tag_id, relationship_type)
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_assets_library ON assets(library_id);
CREATE INDEX IF NOT EXISTS idx_assets_hash ON assets(partial_hash, file_size);
CREATE INDEX IF NOT EXISTS idx_assets_path ON assets(current_path);
CREATE INDEX IF NOT EXISTS idx_assets_missing ON assets(is_missing);
CREATE INDEX IF NOT EXISTS idx_asset_tags_asset ON asset_tags(asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_tags_tag ON asset_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_tags_namespace ON tags(namespace, name);
CREATE INDEX IF NOT EXISTS idx_tag_relationships_tag ON tag_relationships(tag_id);
"""


class AssetDatabase:
    """SQLite database manager for Asset Manager.

    Thread-safe singleton that manages database connections and migrations.
    """

    _instance: Optional["AssetDatabase"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AssetDatabase":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._db_path = self._get_db_path()
        self._local = threading.local()
        self._ensure_directory()
        self._migrate()
        self._initialized = True

    def _get_db_path(self) -> Path:
        """Get database file path."""
        config_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
        return Path(config_dir) / "Commander" / "commander_assets.db"

    def _ensure_directory(self) -> None:
        """Ensure database directory exists."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self._db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            self._local.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection

    @property
    def connection(self) -> sqlite3.Connection:
        """Get current thread's database connection."""
        return self._get_connection()

    def _migrate(self) -> None:
        """Run database migrations."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check current schema version
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if cursor.fetchone() is None:
            # Fresh database, create all tables
            cursor.executescript(SCHEMA_SQL)
            cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            conn.commit()
            return

        # Check version and run migrations if needed
        cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = cursor.fetchone()
        current_version = row[0] if row else 0

        if current_version < SCHEMA_VERSION:
            self._run_migrations(current_version, SCHEMA_VERSION)

    def _run_migrations(self, from_version: int, to_version: int) -> None:
        """Run incremental migrations."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Migration functions for each version
        migrations = {
            # 1: self._migrate_v1,  # Initial schema, no migration needed
        }

        for version in range(from_version + 1, to_version + 1):
            if version in migrations:
                migrations[version](cursor)

        cursor.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (to_version,))
        conn.commit()

    def execute(self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> sqlite3.Cursor:
        """Execute SQL statement."""
        return self.connection.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        """Execute SQL statement with multiple parameter sets."""
        return self.connection.executemany(sql, params_list)

    def fetchone(
        self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> Optional[sqlite3.Row]:
        """Execute SQL and fetch one result."""
        cursor = self.execute(sql, params)
        return cursor.fetchone()

    def fetchall(
        self, sql: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> list[sqlite3.Row]:
        """Execute SQL and fetch all results."""
        cursor = self.execute(sql, params)
        return cursor.fetchall()

    def commit(self) -> None:
        """Commit current transaction."""
        self.connection.commit()

    def rollback(self) -> None:
        """Rollback current transaction."""
        self.connection.rollback()

    def close(self) -> None:
        """Close current thread's connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    @property
    def db_path(self) -> Path:
        """Get database file path."""
        return self._db_path


def get_database() -> AssetDatabase:
    """Get the singleton database instance."""
    return AssetDatabase()
