"""Tests for FileOperations - copy, paste, delete, move, rename."""

import pytest
from pathlib import Path

from commander.core.file_operations import FileOperations, ConflictResolution


class TestCopyPaste:
    """Test copy and paste operations."""

    def test_copy_single_file(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test copying a single file."""
        src_file = source_dir / "file1.txt"

        file_ops.copy_to_clipboard([src_file])
        count = file_ops.paste(dest_dir)

        assert count == 1
        assert (dest_dir / "file1.txt").exists()
        assert (dest_dir / "file1.txt").read_text() == "content1"
        # Original should still exist
        assert src_file.exists()

    def test_copy_multiple_files(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test copying multiple files."""
        files = [source_dir / "file1.txt", source_dir / "file2.txt"]

        file_ops.copy_to_clipboard(files)
        count = file_ops.paste(dest_dir)

        assert count == 2
        assert (dest_dir / "file1.txt").exists()
        assert (dest_dir / "file2.txt").exists()

    def test_copy_directory(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test copying a directory with nested files."""
        subdir = source_dir / "subdir"

        file_ops.copy_to_clipboard([subdir])
        count = file_ops.paste(dest_dir)

        assert count == 1
        assert (dest_dir / "subdir").is_dir()
        assert (dest_dir / "subdir" / "nested.txt").exists()
        assert (dest_dir / "subdir" / "deep" / "deepfile.txt").exists()

    def test_paste_without_clipboard(self, file_ops: FileOperations, dest_dir: Path):
        """Test paste with empty clipboard."""
        count = file_ops.paste(dest_dir)
        assert count == 0


class TestCutPaste:
    """Test cut and paste (move) operations."""

    def test_cut_single_file(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test cutting (moving) a single file."""
        src_file = source_dir / "file1.txt"

        file_ops.cut_to_clipboard([src_file])
        count = file_ops.paste(dest_dir)

        assert count == 1
        assert (dest_dir / "file1.txt").exists()
        # Original should NOT exist after cut
        assert not src_file.exists()

    def test_cut_directory(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test cutting a directory."""
        subdir = source_dir / "subdir"

        file_ops.cut_to_clipboard([subdir])
        count = file_ops.paste(dest_dir)

        assert count == 1
        assert (dest_dir / "subdir").is_dir()
        # Original should NOT exist
        assert not subdir.exists()

    def test_cut_clears_clipboard(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test that cut clears clipboard after paste."""
        src_file = source_dir / "file1.txt"

        file_ops.cut_to_clipboard([src_file])
        file_ops.paste(dest_dir)

        # Clipboard should be empty now
        assert not file_ops.has_clipboard()


class TestConflictResolution:
    """Test conflict resolution during copy/paste."""

    def test_conflict_skip(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test skipping conflicting files."""
        src_file = source_dir / "file1.txt"
        # Create existing file with different content
        (dest_dir / "file1.txt").write_text("existing content")

        file_ops.copy_to_clipboard([src_file])
        count = file_ops.paste(dest_dir, conflict_resolution=ConflictResolution.SKIP)

        assert count == 0  # Skipped
        assert (dest_dir / "file1.txt").read_text() == "existing content"

    def test_conflict_overwrite(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test overwriting conflicting files."""
        src_file = source_dir / "file1.txt"
        (dest_dir / "file1.txt").write_text("existing content")

        file_ops.copy_to_clipboard([src_file])
        count = file_ops.paste(dest_dir, conflict_resolution=ConflictResolution.OVERWRITE)

        assert count == 1
        assert (dest_dir / "file1.txt").read_text() == "content1"

    def test_conflict_rename(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test keeping both files with rename."""
        src_file = source_dir / "file1.txt"
        (dest_dir / "file1.txt").write_text("existing content")

        file_ops.copy_to_clipboard([src_file])
        count = file_ops.paste(dest_dir, conflict_resolution=ConflictResolution.RENAME)

        assert count == 1
        assert (dest_dir / "file1.txt").read_text() == "existing content"
        assert (dest_dir / "file1 (1).txt").exists()
        assert (dest_dir / "file1 (1).txt").read_text() == "content1"

    def test_conflict_rename_multiple(
        self, file_ops: FileOperations, source_dir: Path, dest_dir: Path
    ):
        """Test rename increment when multiple conflicts exist."""
        src_file = source_dir / "file1.txt"
        (dest_dir / "file1.txt").write_text("existing1")
        (dest_dir / "file1 (1).txt").write_text("existing2")

        file_ops.copy_to_clipboard([src_file])
        count = file_ops.paste(dest_dir, conflict_resolution=ConflictResolution.RENAME)

        assert count == 1
        assert (dest_dir / "file1 (2).txt").exists()

    def test_conflict_cancel(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test cancelling operation on conflict."""
        src_file = source_dir / "file1.txt"

        file_ops.copy_to_clipboard([src_file])
        count = file_ops.paste(dest_dir, conflict_resolution=ConflictResolution.CANCEL)

        assert count == 0

    def test_conflict_overwrite_directory(
        self, file_ops: FileOperations, source_dir: Path, dest_dir: Path
    ):
        """Test overwriting existing directory."""
        subdir = source_dir / "subdir"
        # Create existing directory with different content
        existing_dir = dest_dir / "subdir"
        existing_dir.mkdir()
        (existing_dir / "old_file.txt").write_text("old")

        file_ops.copy_to_clipboard([subdir])
        count = file_ops.paste(dest_dir, conflict_resolution=ConflictResolution.OVERWRITE)

        assert count == 1
        # Old file should be gone, new files should exist
        assert not (dest_dir / "subdir" / "old_file.txt").exists()
        assert (dest_dir / "subdir" / "nested.txt").exists()


class TestDirectCopyMove:
    """Test direct copy/move methods (not using clipboard)."""

    def test_direct_copy(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test direct copy without clipboard."""
        files = [source_dir / "file1.txt", source_dir / "file2.txt"]

        count = file_ops.copy(files, dest_dir)

        assert count == 2
        assert (dest_dir / "file1.txt").exists()
        assert (dest_dir / "file2.txt").exists()
        # Originals still exist
        assert (source_dir / "file1.txt").exists()

    def test_direct_move(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test direct move without clipboard."""
        files = [source_dir / "file1.txt", source_dir / "file2.txt"]

        count = file_ops.move(files, dest_dir)

        assert count == 2
        assert (dest_dir / "file1.txt").exists()
        # Originals should NOT exist
        assert not (source_dir / "file1.txt").exists()


class TestDelete:
    """Test delete operations."""

    def test_delete_file(self, file_ops: FileOperations, source_dir: Path):
        """Test deleting a file (to trash)."""
        src_file = source_dir / "file1.txt"

        count = file_ops.delete([src_file])

        assert count == 1
        assert not src_file.exists()

    def test_delete_multiple_files(self, file_ops: FileOperations, source_dir: Path):
        """Test deleting multiple files."""
        files = [source_dir / "file1.txt", source_dir / "file2.txt"]

        count = file_ops.delete(files)

        assert count == 2
        assert not (source_dir / "file1.txt").exists()
        assert not (source_dir / "file2.txt").exists()

    def test_delete_directory(self, file_ops: FileOperations, source_dir: Path):
        """Test deleting a directory."""
        subdir = source_dir / "subdir"

        count = file_ops.delete([subdir])

        assert count == 1
        assert not subdir.exists()

    def test_delete_nonexistent(self, file_ops: FileOperations, source_dir: Path):
        """Test deleting nonexistent file."""
        nonexistent = source_dir / "nonexistent.txt"

        count = file_ops.delete([nonexistent])

        assert count == 0


class TestRename:
    """Test rename operations."""

    def test_rename_file(self, file_ops: FileOperations, source_dir: Path):
        """Test renaming a file."""
        src_file = source_dir / "file1.txt"

        new_path = file_ops.rename(src_file, "renamed.txt")

        assert new_path == source_dir / "renamed.txt"
        assert new_path.exists()
        assert not src_file.exists()

    def test_rename_directory(self, file_ops: FileOperations, source_dir: Path):
        """Test renaming a directory."""
        subdir = source_dir / "subdir"

        new_path = file_ops.rename(subdir, "renamed_dir")

        assert new_path == source_dir / "renamed_dir"
        assert new_path.is_dir()
        assert (new_path / "nested.txt").exists()

    def test_rename_to_existing_fails_or_overwrites(
        self, file_ops: FileOperations, source_dir: Path
    ):
        """Test renaming to existing name - behavior varies by OS."""
        import sys

        src_file = source_dir / "file1.txt"
        original_content = src_file.read_text()

        new_path = file_ops.rename(src_file, "file2.txt")

        if sys.platform == "win32":
            # Windows: rename to existing file fails
            assert new_path is None
            assert src_file.exists()
        else:
            # macOS/Linux: rename overwrites existing file
            assert new_path == source_dir / "file2.txt"
            assert new_path.exists()
            assert new_path.read_text() == original_content
            assert not src_file.exists()


class TestCreateFolder:
    """Test folder creation."""

    def test_create_folder(self, file_ops: FileOperations, dest_dir: Path):
        """Test creating a new folder."""
        new_folder = file_ops.create_folder(dest_dir, "new_folder")

        assert new_folder == dest_dir / "new_folder"
        assert new_folder.is_dir()

    def test_create_folder_conflict(self, file_ops: FileOperations, dest_dir: Path):
        """Test creating folder with existing name fails."""
        (dest_dir / "existing").mkdir()

        result = file_ops.create_folder(dest_dir, "existing")

        assert result is None


class TestFindConflicts:
    """Test conflict detection."""

    def test_find_no_conflicts(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test when no conflicts exist."""
        sources = [source_dir / "file1.txt"]

        conflicts = file_ops.find_conflicts(sources, dest_dir)

        assert len(conflicts) == 0

    def test_find_conflicts(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test finding existing conflicts."""
        (dest_dir / "file1.txt").write_text("existing")
        sources = [source_dir / "file1.txt", source_dir / "file2.txt"]

        conflicts = file_ops.find_conflicts(sources, dest_dir)

        assert len(conflicts) == 1
        assert conflicts[0][0] == source_dir / "file1.txt"
        assert conflicts[0][1] == dest_dir / "file1.txt"


class TestClipboard:
    """Test clipboard operations."""

    def test_has_clipboard_empty(self, file_ops: FileOperations):
        """Test empty clipboard."""
        assert not file_ops.has_clipboard()

    def test_has_clipboard_after_copy(self, file_ops: FileOperations, source_dir: Path):
        """Test clipboard after copy."""
        file_ops.copy_to_clipboard([source_dir / "file1.txt"])
        assert file_ops.has_clipboard()

    def test_get_clipboard_info(self, file_ops: FileOperations, source_dir: Path):
        """Test getting clipboard info."""
        files = [source_dir / "file1.txt"]
        file_ops.copy_to_clipboard(files)

        paths, mode = file_ops.get_clipboard_info()

        assert paths == files
        assert mode == "copy"

    def test_clipboard_mode_cut(self, file_ops: FileOperations, source_dir: Path):
        """Test clipboard mode for cut."""
        file_ops.cut_to_clipboard([source_dir / "file1.txt"])

        _, mode = file_ops.get_clipboard_info()

        assert mode == "cut"


class TestErrorHandling:
    """Test error handling in file operations."""

    def test_copy_nonexistent_file(self, file_ops: FileOperations, dest_dir: Path):
        """Test copying nonexistent file is silently skipped."""
        nonexistent = Path("/nonexistent/file.txt")

        count = file_ops.copy([nonexistent], dest_dir)

        assert count == 0

    def test_move_nonexistent_file(self, file_ops: FileOperations, dest_dir: Path):
        """Test moving nonexistent file is silently skipped."""
        nonexistent = Path("/nonexistent/file.txt")

        count = file_ops.move([nonexistent], dest_dir)

        assert count == 0

    def test_paste_nonexistent_from_clipboard(
        self, file_ops: FileOperations, source_dir: Path, dest_dir: Path
    ):
        """Test pasting file that was deleted after copy."""
        src_file = source_dir / "file1.txt"
        file_ops.copy_to_clipboard([src_file])

        # Delete after copying to clipboard
        src_file.unlink()

        count = file_ops.paste(dest_dir)

        assert count == 0

    def test_rename_nonexistent_file(self, file_ops: FileOperations, source_dir: Path):
        """Test renaming nonexistent file returns None."""
        nonexistent = source_dir / "nonexistent.txt"

        result = file_ops.rename(nonexistent, "new_name.txt")

        assert result is None

    def test_create_folder_invalid_parent(self, file_ops: FileOperations):
        """Test creating folder in nonexistent parent."""
        result = file_ops.create_folder(Path("/nonexistent/parent"), "test")

        assert result is None

    def test_find_conflicts_with_nonexistent_source(self, file_ops: FileOperations, dest_dir: Path):
        """Test finding conflicts when source doesn't exist."""
        nonexistent = Path("/nonexistent/file.txt")

        conflicts = file_ops.find_conflicts([nonexistent], dest_dir)

        assert len(conflicts) == 0


class TestProgressCallback:
    """Test progress callback functionality."""

    def test_copy_with_progress_callback(
        self, file_ops: FileOperations, source_dir: Path, dest_dir: Path
    ):
        """Test copy reports progress."""
        progress_calls = []

        def callback(current: int, total: int, filename: str) -> bool:
            progress_calls.append((current, total, filename))
            return False  # Don't cancel

        file_ops.copy([source_dir / "file1.txt"], dest_dir, progress_callback=callback)

        assert len(progress_calls) > 0

    def test_copy_cancelled_by_callback(
        self, file_ops: FileOperations, source_dir: Path, dest_dir: Path
    ):
        """Test copy can be cancelled by callback."""

        def callback(current: int, total: int, filename: str) -> bool:
            return True  # Cancel immediately

        files = [source_dir / "file1.txt", source_dir / "file2.txt"]
        count = file_ops.copy(files, dest_dir, progress_callback=callback)

        # Should have copied 0 or 1 file before cancel
        assert count <= 1

    def test_move_with_progress_callback(
        self, file_ops: FileOperations, source_dir: Path, dest_dir: Path
    ):
        """Test move reports progress."""
        progress_calls = []

        def callback(current: int, total: int, filename: str) -> bool:
            progress_calls.append((current, total, filename))
            return False

        file_ops.move([source_dir / "file1.txt"], dest_dir, progress_callback=callback)

        assert len(progress_calls) > 0

    def test_paste_with_progress_callback(
        self, file_ops: FileOperations, source_dir: Path, dest_dir: Path
    ):
        """Test paste reports progress."""
        progress_calls = []

        def callback(current: int, total: int, filename: str) -> bool:
            progress_calls.append((current, total, filename))
            return False

        file_ops.copy_to_clipboard([source_dir / "file1.txt"])
        file_ops.paste(dest_dir, progress_callback=callback)

        assert len(progress_calls) > 0

    def test_paste_cut_with_progress_callback(
        self, file_ops: FileOperations, source_dir: Path, dest_dir: Path
    ):
        """Test paste (cut mode) reports progress."""
        progress_calls = []

        def callback(current: int, total: int, filename: str) -> bool:
            progress_calls.append((current, total, filename))
            return False

        file_ops.cut_to_clipboard([source_dir / "file1.txt"])
        file_ops.paste(dest_dir, progress_callback=callback)

        assert len(progress_calls) > 0


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_copy_empty_directory(self, file_ops: FileOperations, temp_dir: Path, dest_dir: Path):
        """Test copying empty directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        count = file_ops.copy([empty_dir], dest_dir)

        assert count == 1
        assert (dest_dir / "empty").is_dir()

    def test_copy_deeply_nested(self, file_ops: FileOperations, source_dir: Path, dest_dir: Path):
        """Test copying deeply nested directory structure."""
        # source_dir/subdir/deep/deepfile.txt already exists from fixture
        subdir = source_dir / "subdir"

        count = file_ops.copy([subdir], dest_dir)

        assert count == 1
        assert (dest_dir / "subdir" / "deep" / "deepfile.txt").exists()

    def test_unique_path_generation(self, file_ops: FileOperations, dest_dir: Path):
        """Test unique path generation for multiple conflicts."""
        # Create file.txt, file (1).txt, file (2).txt
        (dest_dir / "test.txt").write_text("0")
        (dest_dir / "test (1).txt").write_text("1")
        (dest_dir / "test (2).txt").write_text("2")

        unique = file_ops._get_unique_path(dest_dir / "test.txt")

        assert unique == dest_dir / "test (3).txt"

    def test_get_size_of_directory(self, file_ops: FileOperations, source_dir: Path):
        """Test getting size of directory."""
        size = file_ops._get_size(source_dir / "subdir")

        assert size > 0  # Should have content

    def test_get_size_of_file(self, file_ops: FileOperations, source_dir: Path):
        """Test getting size of file."""
        size = file_ops._get_size(source_dir / "file1.txt")

        assert size == len("content1")
