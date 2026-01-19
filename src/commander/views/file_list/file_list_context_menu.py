"""Context menu mixin for file list view."""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QMenu

from commander.views.file_list.file_list_models import MenuShortcutFilter
from commander.utils.i18n import tr


class FileListContextMenuMixin:
    """Mixin providing context menu functionality."""

    # Expected from main class
    _current_path: Path | None
    _viewer: object

    def _show_context_menu(self, pos: QPoint) -> None:
        """Show context menu with custom options."""
        from commander.utils.custom_commands import get_custom_commands_manager

        selected_paths = self.get_selected_paths()

        # Target path: selected item or current folder (for empty space click)
        target_path = selected_paths[0] if selected_paths else self._current_path

        menu = QMenu(self)

        # Open with default app
        if selected_paths:
            open_action = menu.addAction("Open")
            open_action.triggered.connect(lambda: self._open_with_default(selected_paths[0]))

            # Open in New Window (for folders)
            if len(selected_paths) == 1 and selected_paths[0].is_dir():
                new_window_action = menu.addAction("Open in New Window")
                new_window_action.triggered.connect(
                    lambda: self.request_new_window.emit(selected_paths[0])
                )

        # Custom commands - show for selected file OR current folder (empty space click)
        shortcut_actions: dict[str, tuple] = {}  # shortcut -> (cmd, path)
        if target_path and (len(selected_paths) <= 1):
            custom_cmds = get_custom_commands_manager().get_commands_for_path(target_path)
            if custom_cmds:
                menu.addSeparator()
                for cmd in custom_cmds:
                    # Show shortcut in menu name like "Open in Image Viewer(3)"
                    name = cmd.name
                    if cmd.shortcut:
                        name = f"{cmd.name}({cmd.shortcut})"
                        shortcut_actions[cmd.shortcut.upper()] = (cmd, target_path)
                    action = menu.addAction(name)
                    action.triggered.connect(
                        lambda checked, c=cmd, p=target_path: self._run_custom_command(c, p)
                    )

        if selected_paths:
            # Open With submenu (macOS only for now)
            if sys.platform == "darwin" and len(selected_paths) == 1:
                open_with_menu = menu.addMenu("Open With")
                self._populate_open_with_menu(open_with_menu, selected_paths[0])

            if len(selected_paths) == 1:
                menu.addSeparator()

                # Rename (F2)
                rename_action = menu.addAction("Rename")
                rename_action.setShortcut("F2")
                rename_action.triggered.connect(self.start_rename)

                # Get Info
                info_action = menu.addAction("Get Info")
                info_action.triggered.connect(lambda: self._show_info(selected_paths[0]))

            menu.addSeparator()

            # Copy/Cut/Delete
            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(lambda: self._copy_files(selected_paths))

            cut_action = menu.addAction("Cut")
            cut_action.triggered.connect(lambda: self._cut_files(selected_paths))

            # Copy Path
            copy_path_action = menu.addAction("Copy Path")
            copy_path_action.triggered.connect(lambda: self._copy_path(selected_paths))

            menu.addSeparator()

            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self._delete_files(selected_paths))

            menu.addSeparator()

            # Extract All option for archives
            from commander.core.archive_handler import ArchiveManager

            archive_paths = [p for p in selected_paths if ArchiveManager.is_archive(p)]
            if archive_paths:
                extract_action = menu.addAction(f"{tr('extract_all')}(Z)")
                extract_action.triggered.connect(lambda: self._extract_archives(archive_paths))
                shortcut_actions["Z"] = (None, archive_paths)  # Special marker for extract

            # Compress option
            if len(selected_paths) >= 1:
                compress_action = menu.addAction("Compress to ZIP...")
                compress_action.triggered.connect(lambda: self._compress_files(selected_paths))

            # Quick Look (macOS)
            if sys.platform == "darwin" and len(selected_paths) == 1:
                quicklook_action = menu.addAction("Quick Look")
                quicklook_action.triggered.connect(lambda: self._quick_look(selected_paths[0]))

        menu.addSeparator()

        # Paste (always available)
        paste_action = menu.addAction("Paste")
        paste_action.triggered.connect(self._paste_files)

        menu.addSeparator()

        # New folder
        new_folder_action = menu.addAction("New Folder")
        new_folder_action.triggered.connect(self._create_new_folder)

        # New file
        new_file_action = menu.addAction("New File")
        new_file_action.triggered.connect(self._create_new_file)

        menu.addSeparator()

        # Show in Finder/Explorer
        if sys.platform == "darwin":
            reveal_action = menu.addAction("Reveal in Finder")
        elif sys.platform == "win32":
            reveal_action = menu.addAction("Open in Explorer")
        else:
            reveal_action = menu.addAction("Open in File Manager")

        reveal_path = selected_paths[0] if selected_paths else self._current_path
        if reveal_path:
            reveal_action.triggered.connect(lambda: self._reveal_in_finder(reveal_path))

        # Install key event filter for custom command shortcuts
        if shortcut_actions:
            menu.installEventFilter(
                MenuShortcutFilter(
                    menu,
                    shortcut_actions,
                    self._run_custom_command,
                    self._extract_archives,
                )
            )

        view = self._current_view()
        menu.exec(view.mapToGlobal(pos))

    def _populate_open_with_menu(self, menu: QMenu, path: Path) -> None:
        """Populate Open With submenu with available apps."""
        if sys.platform == "darwin":
            try:
                common_apps = [
                    ("TextEdit", "/System/Applications/TextEdit.app"),
                    ("Preview", "/System/Applications/Preview.app"),
                    ("VS Code", "/Applications/Visual Studio Code.app"),
                ]

                for name, app_path in common_apps:
                    if Path(app_path).exists():
                        action = menu.addAction(name)
                        action.triggered.connect(
                            lambda checked, p=app_path: subprocess.run(["open", "-a", p, str(path)])
                        )

                menu.addSeparator()
                other_action = menu.addAction("Other...")
                other_action.triggered.connect(lambda: self._open_with_other(path))

            except Exception:
                other_action = menu.addAction("Choose Application...")
                other_action.triggered.connect(lambda: self._open_with_other(path))
        else:
            other_action = menu.addAction("Choose Application...")
            other_action.triggered.connect(lambda: self._open_with_other(path))

    def _open_with_other(self, path: Path) -> None:
        """Open file with user-selected application."""
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Finder", str(path)])
        elif sys.platform == "win32":
            subprocess.run(["rundll32", "shell32.dll,OpenAs_RunDLL", str(path)])
