"""Custom context menu commands manager."""

import json
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QStandardPaths


@dataclass
class CustomCommand:
    """A custom command for context menu."""

    name: str  # Display name
    command: str  # Command template with {path}, {dir}, {name}, {ext}
    extensions: list[str] = field(default_factory=list)  # Empty = all files
    for_directories: bool = True  # Show for directories
    for_files: bool = True  # Show for files
    enabled: bool = True
    shortcut: str = ""  # Single key shortcut (e.g., "V", "T", "1")

    def matches(self, path: Path) -> bool:
        """Check if this command should be shown for the given path."""
        if not self.enabled:
            return False

        is_dir = path.is_dir()

        if is_dir and not self.for_directories:
            return False
        if not is_dir and not self.for_files:
            return False

        # Check extension filter
        if not is_dir and self.extensions:
            ext = path.suffix.lower().lstrip(".")
            if ext not in [e.lower().lstrip(".") for e in self.extensions]:
                return False

        return True

    def execute(self, path: Path) -> None:
        """Execute the command for the given path."""
        # Replace placeholders
        cmd = self.command
        cmd = cmd.replace("{path}", str(path))
        cmd = cmd.replace("{dir}", str(path.parent if path.is_file() else path))
        cmd = cmd.replace("{name}", path.name)
        cmd = cmd.replace("{stem}", path.stem)
        cmd = cmd.replace("{ext}", path.suffix.lstrip("."))

        # Execute
        if sys.platform == "win32":
            subprocess.Popen(cmd, shell=True)
        else:
            subprocess.Popen(cmd, shell=True)


class CustomCommandsManager:
    """Manages custom commands with persistence."""

    _instance: Optional["CustomCommandsManager"] = None

    def __init__(self):
        self._commands: list[CustomCommand] = []
        self._config_path = self._get_config_path()
        self._load()

    @classmethod
    def instance(cls) -> "CustomCommandsManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_config_path(self) -> Path:
        """Get path to config file."""
        config_dir = Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        )
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "custom_commands.json"

    def _load(self) -> None:
        """Load commands from config file."""
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._commands = [CustomCommand(**cmd) for cmd in data]
                    return
            except (json.JSONDecodeError, TypeError, KeyError):
                pass  # Fall through to defaults

        # Initialize with default commands
        self._commands = self._get_default_commands()
        self._save()

    def _save(self) -> None:
        """Save commands to config file."""
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump([asdict(cmd) for cmd in self._commands], f, indent=2, ensure_ascii=False)

    def _get_default_commands(self) -> list[CustomCommand]:
        """Get default commands based on OS."""
        # Common image extensions (including SVG)
        image_exts = [
            "png",
            "jpg",
            "jpeg",
            "gif",
            "bmp",
            "webp",
            "tiff",
            "tif",
            "ico",
            "psd",
            "psb",
            "svg",
            "svgz",
            "heic",
            "heif",
            "avif",
        ]
        archive_exts = ["zip", "rar", "7z", "tar", "gz", "bz2"]
        # Image viewer supports both images and archives (to view images inside archives)
        image_viewer_exts = image_exts + archive_exts

        # Built-in commands (special: handled internally)
        image_viewer_cmd = CustomCommand(
            name="Open in Image Viewer",
            command="__builtin__:image_viewer",
            extensions=image_viewer_exts,
            for_directories=True,
            for_files=True,
            shortcut="3",
        )

        extract_cmd = CustomCommand(
            name="Extract Here",
            command="__builtin__:extract",
            extensions=archive_exts,
            for_directories=False,
            for_files=True,
            shortcut="Z",
        )

        commands = [image_viewer_cmd, extract_cmd]

        if sys.platform == "darwin":
            # macOS defaults
            commands += [
                CustomCommand(
                    name="Open with VS Code",
                    command='open -a "Visual Studio Code" "{path}"',
                    extensions=[],
                    for_directories=True,
                    for_files=True,
                    shortcut="V",
                ),
                CustomCommand(
                    name="Open Terminal Here",
                    command='open -a Terminal "{dir}"',
                    extensions=[],
                    for_directories=True,
                    for_files=True,
                    shortcut="T",
                ),
                CustomCommand(
                    name="Open iTerm Here",
                    command='open -a iTerm "{dir}"',
                    extensions=[],
                    for_directories=True,
                    for_files=True,
                    enabled=False,
                    shortcut="I",
                ),
            ]
        elif sys.platform == "win32":
            # Windows defaults
            commands += [
                CustomCommand(
                    name="Open with VS Code",
                    command='code "{path}"',
                    extensions=[],
                    for_directories=True,
                    for_files=True,
                    shortcut="V",
                ),
                CustomCommand(
                    name="Open Git Bash Here",
                    command='"C:\\Program Files\\Git\\git-bash.exe" --cd="{dir}"',
                    extensions=[],
                    for_directories=True,
                    for_files=True,
                    shortcut="G",
                ),
                CustomCommand(
                    name="Open CMD Here",
                    command='start cmd /k "cd /d {dir}"',
                    extensions=[],
                    for_directories=True,
                    for_files=True,
                    shortcut="C",
                ),
                CustomCommand(
                    name="Open PowerShell Here",
                    command="start powershell -NoExit -Command \"cd '{dir}'\"",
                    extensions=[],
                    for_directories=True,
                    for_files=True,
                ),
                CustomCommand(
                    name="Open with Notepad",
                    command='notepad "{path}"',
                    extensions=["txt", "log", "ini", "cfg", "md"],
                    for_directories=False,
                    for_files=True,
                ),
            ]
        else:
            # Linux defaults
            commands += [
                CustomCommand(
                    name="Open with VS Code",
                    command='code "{path}"',
                    extensions=[],
                    for_directories=True,
                    for_files=True,
                ),
                CustomCommand(
                    name="Open Terminal Here",
                    command='gnome-terminal --working-directory="{dir}"',
                    extensions=[],
                    for_directories=True,
                    for_files=True,
                ),
                CustomCommand(
                    name="Open with gedit",
                    command='gedit "{path}"',
                    extensions=["txt", "py", "js", "json", "xml", "html", "css", "md"],
                    for_directories=False,
                    for_files=True,
                ),
            ]

        return commands

    def is_builtin_command(self, command: CustomCommand) -> bool:
        """Check if command is a built-in command."""
        return command.command.startswith("__builtin__:")

    def get_commands(self) -> list[CustomCommand]:
        """Get all commands."""
        return self._commands.copy()

    def get_commands_for_path(self, path: Path) -> list[CustomCommand]:
        """Get commands that match the given path."""
        return [cmd for cmd in self._commands if cmd.matches(path)]

    def add_command(self, command: CustomCommand) -> None:
        """Add a new command."""
        self._commands.append(command)
        self._save()

    def update_command(self, index: int, command: CustomCommand) -> None:
        """Update command at index."""
        if 0 <= index < len(self._commands):
            self._commands[index] = command
            self._save()

    def remove_command(self, index: int) -> None:
        """Remove command at index."""
        if 0 <= index < len(self._commands):
            del self._commands[index]
            self._save()

    def move_command(self, from_index: int, to_index: int) -> None:
        """Move command from one position to another."""
        if 0 <= from_index < len(self._commands) and 0 <= to_index < len(self._commands):
            cmd = self._commands.pop(from_index)
            self._commands.insert(to_index, cmd)
            self._save()

    def reset_to_defaults(self) -> None:
        """Reset all commands to defaults."""
        self._commands = self._get_default_commands()
        self._save()


def get_custom_commands_manager() -> CustomCommandsManager:
    """Get the singleton CustomCommandsManager instance."""
    return CustomCommandsManager.instance()
