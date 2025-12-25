"""Undo/Redo manager for file operations."""

import shutil
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable

import send2trash

from PySide6.QtCore import QObject, Signal

from commander.utils.settings import Settings


class ActionType(Enum):
    """Types of undoable actions."""

    COPY = auto()
    MOVE = auto()
    DELETE = auto()
    RENAME = auto()
    CREATE_FOLDER = auto()


@dataclass
class UndoableAction:
    """Represents an undoable file operation."""

    action_type: ActionType
    # For COPY/MOVE: source paths that were copied/moved
    # For DELETE: paths that were deleted
    # For RENAME: [old_path]
    # For CREATE_FOLDER: [created_path]
    source_paths: list[Path] = field(default_factory=list)
    # For COPY/MOVE: destination paths that were created
    # For DELETE: backup location (trash)
    # For RENAME: [new_path]
    # For CREATE_FOLDER: empty
    dest_paths: list[Path] = field(default_factory=list)
    # Additional info
    description: str = ""


class UndoManager(QObject):
    """Manages undo/redo stack for file operations."""

    # Signals
    undo_available = Signal(bool)
    redo_available = Signal(bool)
    action_performed = Signal(str)  # Description of action

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._settings = Settings()
        self._undo_stack: list[UndoableAction] = []
        self._redo_stack: list[UndoableAction] = []
        self._max_stack_size = self._settings.load_undo_stack_size()
        self._initialized = True

    def record_copy(self, sources: list[Path], destinations: list[Path]):
        """Record a copy operation."""
        action = UndoableAction(
            action_type=ActionType.COPY,
            source_paths=sources.copy(),
            dest_paths=destinations.copy(),
            description=f"Copy {len(sources)} item(s)",
        )
        self._push_action(action)

    def record_move(self, sources: list[Path], destinations: list[Path]):
        """Record a move operation."""
        action = UndoableAction(
            action_type=ActionType.MOVE,
            source_paths=sources.copy(),
            dest_paths=destinations.copy(),
            description=f"Move {len(sources)} item(s)",
        )
        self._push_action(action)

    def record_delete(self, paths: list[Path]):
        """Record a delete operation."""
        action = UndoableAction(
            action_type=ActionType.DELETE,
            source_paths=paths.copy(),
            description=f"Delete {len(paths)} item(s)",
        )
        self._push_action(action)

    def record_rename(self, old_path: Path, new_path: Path):
        """Record a rename operation."""
        action = UndoableAction(
            action_type=ActionType.RENAME,
            source_paths=[old_path],
            dest_paths=[new_path],
            description=f"Rename {old_path.name} → {new_path.name}",
        )
        self._push_action(action)

    def record_create_folder(self, path: Path):
        """Record a folder creation."""
        action = UndoableAction(
            action_type=ActionType.CREATE_FOLDER,
            source_paths=[path],
            description=f"Create folder {path.name}",
        )
        self._push_action(action)

    def _push_action(self, action: UndoableAction):
        """Push action to undo stack."""
        self._undo_stack.append(action)
        self._redo_stack.clear()  # Clear redo on new action

        # Limit stack size
        if len(self._undo_stack) > self._max_stack_size:
            self._undo_stack.pop(0)

        self._emit_signals()

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0

    def get_undo_description(self) -> str:
        """Get description of next undo action."""
        if self._undo_stack:
            return self._undo_stack[-1].description
        return ""

    def get_redo_description(self) -> str:
        """Get description of next redo action."""
        if self._redo_stack:
            return self._redo_stack[-1].description
        return ""

    def undo(self) -> bool:
        """Undo the last action. Returns True if successful."""
        if not self._undo_stack:
            return False

        action = self._undo_stack.pop()
        success = False

        try:
            if action.action_type == ActionType.COPY:
                success = self._undo_copy(action)
            elif action.action_type == ActionType.MOVE:
                success = self._undo_move(action)
            elif action.action_type == ActionType.DELETE:
                # Cannot truly undo delete (items in trash)
                self.action_performed.emit("Cannot undo delete (items in Trash)")
                success = False
            elif action.action_type == ActionType.RENAME:
                success = self._undo_rename(action)
            elif action.action_type == ActionType.CREATE_FOLDER:
                success = self._undo_create_folder(action)

            if success:
                self._redo_stack.append(action)
                self.action_performed.emit(f"Undo: {action.description}")
        except Exception as e:
            self.action_performed.emit(f"Undo failed: {e}")
            success = False

        self._emit_signals()
        return success

    def redo(self) -> bool:
        """Redo the last undone action. Returns True if successful."""
        if not self._redo_stack:
            return False

        action = self._redo_stack.pop()
        success = False

        try:
            if action.action_type == ActionType.COPY:
                success = self._redo_copy(action)
            elif action.action_type == ActionType.MOVE:
                success = self._redo_move(action)
            elif action.action_type == ActionType.RENAME:
                success = self._redo_rename(action)
            elif action.action_type == ActionType.CREATE_FOLDER:
                success = self._redo_create_folder(action)

            if success:
                self._undo_stack.append(action)
                self.action_performed.emit(f"Redo: {action.description}")
        except Exception as e:
            self.action_performed.emit(f"Redo failed: {e}")
            success = False

        self._emit_signals()
        return success

    def _undo_copy(self, action: UndoableAction) -> bool:
        """Undo copy by deleting copied files."""
        for dest in action.dest_paths:
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(str(dest))
                else:
                    dest.unlink()
        return True

    def _redo_copy(self, action: UndoableAction) -> bool:
        """Redo copy by copying files again."""
        for src, dst in zip(action.source_paths, action.dest_paths):
            if src.exists() and not dst.exists():
                if src.is_dir():
                    shutil.copytree(str(src), str(dst))
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(dst))
        return True

    def _undo_move(self, action: UndoableAction) -> bool:
        """Undo move by moving files back."""
        for src, dst in zip(action.source_paths, action.dest_paths):
            if dst.exists():
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst), str(src))
        return True

    def _redo_move(self, action: UndoableAction) -> bool:
        """Redo move by moving files again."""
        for src, dst in zip(action.source_paths, action.dest_paths):
            if src.exists() and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
        return True

    def _undo_rename(self, action: UndoableAction) -> bool:
        """Undo rename by renaming back."""
        old_path = action.source_paths[0]
        new_path = action.dest_paths[0]
        if new_path.exists():
            new_path.rename(old_path)
            return True
        return False

    def _redo_rename(self, action: UndoableAction) -> bool:
        """Redo rename."""
        old_path = action.source_paths[0]
        new_path = action.dest_paths[0]
        if old_path.exists():
            old_path.rename(new_path)
            return True
        return False

    def _undo_create_folder(self, action: UndoableAction) -> bool:
        """Undo folder creation by deleting it (if empty)."""
        path = action.source_paths[0]
        if path.exists() and path.is_dir():
            try:
                path.rmdir()  # Only works if empty
                return True
            except OSError:
                # Folder not empty - move to trash instead
                send2trash.send2trash(str(path))
                return True
        return False

    def _redo_create_folder(self, action: UndoableAction) -> bool:
        """Redo folder creation."""
        path = action.source_paths[0]
        if not path.exists():
            path.mkdir(parents=True)
            return True
        return False

    def _emit_signals(self):
        """Emit availability signals."""
        self.undo_available.emit(self.can_undo())
        self.redo_available.emit(self.can_redo())

    def clear(self):
        """Clear all undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._emit_signals()


# Global instance accessor
def get_undo_manager() -> UndoManager:
    """Get the global undo manager instance."""
    return UndoManager()
