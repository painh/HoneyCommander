"""Asset Manager - Library and metadata management for game assets."""

from .database import AssetDatabase, get_database
from .hasher import PartialHasher, compute_partial_hash
from .library import Library, Asset, LibraryManager, get_library_manager
from .tag_system import Tag, TagManager, get_tag_manager
from .scanner import LibraryScanner, AssetVerifier, scan_library_sync, ASSET_EXTENSIONS

__all__ = [
    "AssetDatabase",
    "get_database",
    "PartialHasher",
    "compute_partial_hash",
    "Library",
    "Asset",
    "LibraryManager",
    "get_library_manager",
    "Tag",
    "TagManager",
    "get_tag_manager",
    "LibraryScanner",
    "AssetVerifier",
    "scan_library_sync",
    "ASSET_EXTENSIONS",
]
