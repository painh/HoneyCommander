"""Partial file hashing for file identification.

Uses a fast partial hash algorithm that reads only a small portion of the file
(first 64KB + middle 64KB + last 64KB + file size) to create a unique identifier.
This allows tracking files even when they are moved or renamed.
"""

import hashlib
from pathlib import Path
from typing import Optional


# Size of each chunk to read (64KB)
CHUNK_SIZE = 64 * 1024


class PartialHasher:
    """Compute partial hashes for file identification.

    The partial hash is computed from:
    - File size (8 bytes, little-endian)
    - First 64KB of the file
    - Middle 64KB of the file (if file > 128KB)
    - Last 64KB of the file (if file > 64KB)

    This provides a fast, unique identifier for files that:
    - Works well with large files (only reads ~192KB max)
    - Has extremely low collision probability
    - Changes if file content changes
    """

    def __init__(self, algorithm: str = "sha256") -> None:
        """Initialize hasher with specified algorithm.

        Args:
            algorithm: Hash algorithm to use (default: sha256)
        """
        self.algorithm = algorithm

    def compute(self, path: Path) -> Optional[tuple[str, int]]:
        """Compute partial hash for a file.

        Args:
            path: Path to the file

        Returns:
            Tuple of (hash_hex, file_size) or None if file cannot be read
        """
        try:
            return compute_partial_hash(path, self.algorithm)
        except (OSError, IOError):
            return None


def compute_partial_hash(path: Path, algorithm: str = "sha256") -> tuple[str, int]:
    """Compute partial hash for a file.

    Args:
        path: Path to the file
        algorithm: Hash algorithm to use (default: sha256)

    Returns:
        Tuple of (hash_hex, file_size)

    Raises:
        OSError: If file cannot be read
        IOError: If file cannot be read
    """
    file_size = path.stat().st_size

    hasher = hashlib.new(algorithm)

    # Include file size in hash to further reduce collision probability
    hasher.update(file_size.to_bytes(8, "little"))

    if file_size == 0:
        # Empty file - just return hash of size (which is 0)
        return hasher.hexdigest(), file_size

    with open(path, "rb") as f:
        # Read first chunk
        first_chunk = f.read(CHUNK_SIZE)
        hasher.update(first_chunk)

        # Read middle chunk if file is large enough
        if file_size > CHUNK_SIZE * 2:
            middle_pos = (file_size // 2) - (CHUNK_SIZE // 2)
            f.seek(middle_pos)
            middle_chunk = f.read(CHUNK_SIZE)
            hasher.update(middle_chunk)

        # Read last chunk if file is large enough and different from first
        if file_size > CHUNK_SIZE:
            f.seek(-CHUNK_SIZE, 2)  # Seek from end
            last_chunk = f.read(CHUNK_SIZE)
            hasher.update(last_chunk)

    return hasher.hexdigest(), file_size


def verify_hash(path: Path, expected_hash: str, expected_size: int) -> bool:
    """Verify if a file matches the expected hash and size.

    Args:
        path: Path to the file
        expected_hash: Expected hash value
        expected_size: Expected file size

    Returns:
        True if file matches, False otherwise
    """
    try:
        actual_hash, actual_size = compute_partial_hash(path)
        return actual_hash == expected_hash and actual_size == expected_size
    except (OSError, IOError):
        return False


def find_file_by_hash(
    directory: Path,
    target_hash: str,
    target_size: int,
    recursive: bool = True,
) -> Optional[Path]:
    """Find a file in directory matching the given hash and size.

    Useful for finding moved files.

    Args:
        directory: Directory to search in
        target_hash: Hash to match
        target_size: File size to match
        recursive: Whether to search recursively

    Returns:
        Path to matching file or None if not found
    """
    try:
        iterator = directory.rglob("*") if recursive else directory.glob("*")

        for path in iterator:
            if not path.is_file():
                continue

            # Quick size check first (fast)
            try:
                if path.stat().st_size != target_size:
                    continue
            except OSError:
                continue

            # Hash check (slower, only if size matches)
            try:
                file_hash, file_size = compute_partial_hash(path)
                if file_hash == target_hash and file_size == target_size:
                    return path
            except (OSError, IOError):
                continue

        return None
    except OSError:
        return None
