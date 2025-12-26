"""Tests for UndoManager - undo/redo operations."""

import pytest
from pathlib import Path

from commander.core.undo_manager import UndoManager, ActionType


class TestUndoCopy:
    """Test undo/redo for copy operations."""

    def test_undo_copy_deletes_copied_files(
        self, undo_manager: UndoManager, source_dir: Path, dest_dir: Path
    ):
        """Test that undoing copy deletes the copied files."""
        src_file = source_dir / "file1.txt"
        dst_file = dest_dir / "file1.txt"

        # Simulate copy
        dst_file.write_text(src_file.read_text())
        undo_manager.record_copy([src_file], [dst_file])

        assert undo_manager.can_undo()
        undo_manager.undo()

        # Copied file should be deleted
        assert not dst_file.exists()
        # Source should still exist
        assert src_file.exists()

    def test_redo_copy_restores_files(
        self, undo_manager: UndoManager, source_dir: Path, dest_dir: Path
    ):
        """Test that redo copy restores the files."""
        src_file = source_dir / "file1.txt"
        dst_file = dest_dir / "file1.txt"

        # Simulate copy, then undo
        dst_file.write_text(src_file.read_text())
        undo_manager.record_copy([src_file], [dst_file])
        undo_manager.undo()

        assert undo_manager.can_redo()
        undo_manager.redo()

        # File should be restored
        assert dst_file.exists()
        assert dst_file.read_text() == "content1"


class TestUndoMove:
    """Test undo/redo for move operations."""

    def test_undo_move_restores_original(
        self, undo_manager: UndoManager, source_dir: Path, dest_dir: Path
    ):
        """Test that undoing move restores the original file."""
        src_file = source_dir / "file1.txt"
        dst_file = dest_dir / "file1.txt"
        original_content = src_file.read_text()

        # Simulate move
        dst_file.write_text(original_content)
        src_file.unlink()
        undo_manager.record_move([src_file], [dst_file])

        undo_manager.undo()

        # Original should be restored
        assert src_file.exists()
        assert src_file.read_text() == original_content
        # Destination should be gone
        assert not dst_file.exists()

    def test_redo_move(self, undo_manager: UndoManager, source_dir: Path, dest_dir: Path):
        """Test redo move."""
        src_file = source_dir / "file1.txt"
        dst_file = dest_dir / "file1.txt"

        # Simulate move, then undo
        original_content = src_file.read_text()
        dst_file.write_text(original_content)
        src_file.unlink()
        undo_manager.record_move([src_file], [dst_file])
        undo_manager.undo()

        undo_manager.redo()

        # File should be moved again
        assert dst_file.exists()
        assert not src_file.exists()


class TestUndoRename:
    """Test undo/redo for rename operations."""

    def test_undo_rename(self, undo_manager: UndoManager, source_dir: Path):
        """Test undoing a rename."""
        old_path = source_dir / "file1.txt"
        new_path = source_dir / "renamed.txt"

        # Simulate rename
        old_path.rename(new_path)
        undo_manager.record_rename(old_path, new_path)

        undo_manager.undo()

        # Should be renamed back
        assert old_path.exists()
        assert not new_path.exists()

    def test_redo_rename(self, undo_manager: UndoManager, source_dir: Path):
        """Test redo rename."""
        old_path = source_dir / "file1.txt"
        new_path = source_dir / "renamed.txt"

        # Simulate rename, then undo
        old_path.rename(new_path)
        undo_manager.record_rename(old_path, new_path)
        undo_manager.undo()

        undo_manager.redo()

        # Should be renamed again
        assert new_path.exists()
        assert not old_path.exists()


class TestUndoCreateFolder:
    """Test undo/redo for folder creation."""

    def test_undo_create_empty_folder(self, undo_manager: UndoManager, dest_dir: Path):
        """Test undoing empty folder creation."""
        new_folder = dest_dir / "new_folder"

        # Simulate create folder
        new_folder.mkdir()
        undo_manager.record_create_folder(new_folder)

        undo_manager.undo()

        # Folder should be deleted
        assert not new_folder.exists()

    def test_redo_create_folder(self, undo_manager: UndoManager, dest_dir: Path):
        """Test redo folder creation."""
        new_folder = dest_dir / "new_folder"

        # Simulate create folder, then undo
        new_folder.mkdir()
        undo_manager.record_create_folder(new_folder)
        undo_manager.undo()

        undo_manager.redo()

        # Folder should be recreated
        assert new_folder.exists()
        assert new_folder.is_dir()


class TestUndoDelete:
    """Test that delete cannot be undone (items in trash)."""

    def test_delete_cannot_undo(self, undo_manager: UndoManager, source_dir: Path):
        """Test that delete records but cannot undo."""
        deleted_file = source_dir / "file1.txt"

        # Record delete (file already gone)
        undo_manager.record_delete([deleted_file])

        # Can "undo" but it won't restore
        result = undo_manager.undo()

        assert not result  # Should return False


class TestUndoStack:
    """Test undo/redo stack behavior."""

    def test_undo_clears_redo_stack(self, undo_manager: UndoManager, source_dir: Path):
        """Test that new action clears redo stack."""
        old_path = source_dir / "file1.txt"
        new_path = source_dir / "renamed.txt"

        # Do something, undo it
        old_path.rename(new_path)
        undo_manager.record_rename(old_path, new_path)
        undo_manager.undo()

        assert undo_manager.can_redo()

        # Do a new action - should clear redo
        another_path = source_dir / "file2.txt"
        new_name = source_dir / "file2_renamed.txt"
        another_path.rename(new_name)
        undo_manager.record_rename(another_path, new_name)

        assert not undo_manager.can_redo()

    def test_multiple_undo_redo(self, undo_manager: UndoManager, source_dir: Path):
        """Test multiple undo/redo operations."""
        file1 = source_dir / "file1.txt"
        file2 = source_dir / "file2.txt"
        renamed1 = source_dir / "r1.txt"
        renamed2 = source_dir / "r2.txt"

        # Two renames
        file1.rename(renamed1)
        undo_manager.record_rename(file1, renamed1)
        file2.rename(renamed2)
        undo_manager.record_rename(file2, renamed2)

        # Undo both
        undo_manager.undo()  # Undo file2 rename
        undo_manager.undo()  # Undo file1 rename

        assert file1.exists()
        assert file2.exists()
        assert not renamed1.exists()
        assert not renamed2.exists()

        # Redo both
        undo_manager.redo()
        undo_manager.redo()

        assert not file1.exists()
        assert not file2.exists()
        assert renamed1.exists()
        assert renamed2.exists()

    def test_stack_size_limit(self, undo_manager: UndoManager, dest_dir: Path):
        """Test that stack doesn't grow beyond limit."""
        undo_manager._max_stack_size = 5

        # Create 10 folders
        for i in range(10):
            folder = dest_dir / f"folder{i}"
            folder.mkdir()
            undo_manager.record_create_folder(folder)

        # Only last 5 should be undoable
        assert len(undo_manager._undo_stack) == 5

    def test_cannot_undo_empty(self, undo_manager: UndoManager):
        """Test undo on empty stack."""
        assert not undo_manager.can_undo()
        assert not undo_manager.undo()

    def test_cannot_redo_empty(self, undo_manager: UndoManager):
        """Test redo on empty stack."""
        assert not undo_manager.can_redo()
        assert not undo_manager.redo()

    def test_clear_stacks(self, undo_manager: UndoManager, dest_dir: Path):
        """Test clearing undo/redo stacks."""
        folder = dest_dir / "test"
        folder.mkdir()
        undo_manager.record_create_folder(folder)
        undo_manager.undo()

        assert undo_manager.can_redo()

        undo_manager.clear()

        assert not undo_manager.can_undo()
        assert not undo_manager.can_redo()


class TestUndoDescriptions:
    """Test undo/redo descriptions."""

    def test_undo_description(self, undo_manager: UndoManager, source_dir: Path):
        """Test getting undo description."""
        undo_manager.record_copy([source_dir / "file1.txt"], [source_dir / "copy.txt"])

        desc = undo_manager.get_undo_description()

        assert "Copy" in desc

    def test_redo_description(self, undo_manager: UndoManager, dest_dir: Path):
        """Test getting redo description."""
        folder = dest_dir / "test"
        folder.mkdir()
        undo_manager.record_create_folder(folder)
        undo_manager.undo()

        desc = undo_manager.get_redo_description()

        assert "folder" in desc.lower()
