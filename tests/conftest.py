"""Pytest fixtures for Commander tests."""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmp = Path(tempfile.mkdtemp())
    yield tmp
    # Cleanup
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def source_dir(temp_dir: Path):
    """Create a source directory with test files."""
    src = temp_dir / "source"
    src.mkdir()

    # Create test files
    (src / "file1.txt").write_text("content1")
    (src / "file2.txt").write_text("content2")
    (src / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    # Create subdirectory with files
    subdir = src / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested content")
    (subdir / "deep").mkdir()
    (subdir / "deep" / "deepfile.txt").write_text("deep content")

    return src


@pytest.fixture
def dest_dir(temp_dir: Path):
    """Create a destination directory."""
    dst = temp_dir / "dest"
    dst.mkdir()
    return dst


@pytest.fixture
def file_ops():
    """Get a fresh FileOperations instance."""
    from commander.core.file_operations import FileOperations

    # Reset singleton for testing
    FileOperations._instance = None
    ops = FileOperations()
    yield ops
    # Cleanup
    FileOperations._instance = None


@pytest.fixture
def undo_manager():
    """Get a fresh UndoManager instance."""
    from commander.core.undo_manager import UndoManager

    # Reset singleton for testing
    UndoManager._instance = None
    mgr = UndoManager()
    yield mgr
    # Cleanup
    UndoManager._instance = None
