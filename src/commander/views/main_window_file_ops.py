"""File operations mixin for main window."""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QInputDialog

from commander.core.undo_manager import get_undo_manager
from commander.utils.i18n import tr


class MainWindowFileOpsMixin:
    """Mixin providing file operations for main window."""

    # Expected from main class
    _tab_manager: object
    _file_ops: object
    _status_bar: object
    _settings: object
    _undo_action: object
    _redo_action: object

    def _on_item_activated(self, path: Path):
        """Handle file activation (non-directory)."""
        from commander.core.archive_handler import ArchiveManager

        # Check for macOS app bundle
        is_app_bundle = sys.platform == "darwin" and path.suffix.lower() == ".app"

        if path.is_dir() and not is_app_bundle:
            # This shouldn't happen as TabContentWidget handles directories
            tab = self._tab_manager.get_current_tab()
            if tab:
                tab.navigate_to(path)
        elif ArchiveManager.is_archive(path):
            self._open_archive(path)
        elif self._is_image(path):
            self._open_image_viewer(path)
        else:
            # Open with system default app
            if sys.platform == "darwin":
                subprocess.run(["open", str(path)])
            elif sys.platform == "win32":
                import os

                os.startfile(str(path))
            else:
                subprocess.run(["xdg-open", str(path)])

    def _is_image(self, path: Path) -> bool:
        """Check if path is an image file."""
        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".tiff",
            ".ico",
            ".psd",
            ".psb",
        }
        return path.suffix.lower() in image_extensions

    def _open_image_viewer(self, path: Path):
        """Open fullscreen image viewer."""
        from commander.views.viewer import FullscreenImageViewer

        tab = self._tab_manager.get_current_tab()
        if not tab:
            return

        current_path = tab.current_path
        images = [p for p in current_path.iterdir() if p.is_file() and self._is_image(p)]
        images.sort()

        self._viewer = FullscreenImageViewer(self)
        self._viewer.show_image(path, images)

    def _open_archive(self, path: Path):
        """Open archive browser."""
        from commander.views.archive_browser import ArchiveBrowser
        from commander.core.archive_handler import ArchiveManager
        from PySide6.QtWidgets import QMessageBox

        tab = self._tab_manager.get_current_tab()

        threshold_mb = self._settings.load_archive_size_threshold()
        if threshold_mb > 0:
            try:
                file_size_mb = path.stat().st_size / (1024 * 1024)
                if file_size_mb >= threshold_mb:
                    if file_size_mb >= 1024:
                        size_str = f"{file_size_mb / 1024:.1f} GB"
                    else:
                        size_str = f"{file_size_mb:.1f} MB"

                    msg = QMessageBox(self)
                    msg.setWindowTitle(tr("archive_large_title"))
                    msg.setText(tr("archive_large_message").replace("{size}", size_str))
                    msg.setIcon(QMessageBox.Question)

                    extract_btn = msg.addButton(tr("archive_extract"), QMessageBox.AcceptRole)
                    browse_btn = msg.addButton(tr("archive_browse"), QMessageBox.RejectRole)
                    msg.addButton(tr("cancel"), QMessageBox.RejectRole)

                    msg.exec()

                    if msg.clickedButton() == extract_btn:
                        extract_dir = ArchiveManager.smart_extract(path, path.parent)
                        if tab:
                            tab.navigate_to(extract_dir)
                        return
                    elif msg.clickedButton() == browse_btn:
                        pass
                    else:
                        return
            except OSError:
                pass

        self._archive_browser = ArchiveBrowser(path, self)
        self._archive_browser.show()

    def _on_files_dropped(self, paths: list[Path], destination: Path):
        """Handle files dropped onto folder tree."""
        from PySide6.QtWidgets import QMessageBox
        from commander.widgets.progress_dialog import ProgressDialog

        paths_to_copy = [p for p in paths if p.parent != destination]
        if not paths_to_copy:
            return

        reply = QMessageBox.question(
            self,
            tr("drop_files"),
            tr("drop_copy_or_move").format(count=len(paths_to_copy)),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Cancel:
            return

        if reply == QMessageBox.StandardButton.Yes:
            dialog = ProgressDialog("copy", paths_to_copy, destination, self)
            dialog.exec()
        else:
            dialog = ProgressDialog("move", paths_to_copy, destination, self)
            dialog.exec()

        self._refresh()

    def _get_focused_paths(self) -> list[Path]:
        """Get selected paths from the focused panel."""
        tab = self._tab_manager.get_current_tab()
        if not tab:
            return []

        if tab.folder_tree.hasFocus():
            path = tab.folder_tree.get_selected_path()
            return [path] if path else []
        return tab.get_selected_paths()

    def _copy_selected(self):
        """Copy selected items to clipboard."""
        paths = self._get_focused_paths()
        if paths:
            self._file_ops.copy_to_clipboard(paths)
            self._status_bar.showMessage(f"Copied {len(paths)} item(s)")

    def _cut_selected(self):
        """Cut selected items to clipboard."""
        paths = self._get_focused_paths()
        if paths:
            self._file_ops.cut_to_clipboard(paths)
            self._status_bar.showMessage(f"Cut {len(paths)} item(s)")

    def _paste(self):
        """Paste items from clipboard."""
        from commander.widgets.progress_dialog import ProgressDialog

        tab = self._tab_manager.get_current_tab()
        if not tab:
            return

        if not self._file_ops.has_clipboard():
            self._status_bar.showMessage("Nothing to paste")
            return

        dialog = ProgressDialog("paste", [], tab.current_path, self)
        result = dialog.exec()

        if result:
            count = dialog.get_result()
            self._refresh()
            if count > 0:
                self._status_bar.showMessage(f"Pasted {count} item(s)")
            else:
                self._status_bar.showMessage("Paste cancelled")

    def _delete_selected(self):
        """Delete selected items."""
        tab = self._tab_manager.get_current_tab()
        if not tab:
            return

        paths = tab.get_selected_paths()
        if paths:
            count = self._file_ops.delete(paths)
            self._refresh()
            self._status_bar.showMessage(f"Deleted {count} item(s)")

    def _rename_selected(self):
        """Rename selected item."""
        tab = self._tab_manager.get_current_tab()
        if tab:
            tab.file_list.start_rename()

    def _undo(self):
        """Undo last file operation."""
        get_undo_manager().undo()

    def _redo(self):
        """Redo last undone operation."""
        get_undo_manager().redo()

    def _create_new_folder(self):
        """Create a new folder."""
        tab = self._tab_manager.get_current_tab()
        if not tab:
            return

        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            result = self._file_ops.create_folder(tab.current_path, name)
            if result:
                self._refresh()
                self._status_bar.showMessage(f"Created folder: {name}")
            else:
                self._status_bar.showMessage(f"Error creating folder: {name}")

    # === Undo/Redo ===

    def _on_undo_available(self, available: bool):
        """Update undo action state."""
        self._undo_action.setEnabled(available)
        if available:
            desc = get_undo_manager().get_undo_description()
            self._undo_action.setText(f"Undo {desc}")
        else:
            self._undo_action.setText("Undo")

    def _on_redo_available(self, available: bool):
        """Update redo action state."""
        self._redo_action.setEnabled(available)
        if available:
            desc = get_undo_manager().get_redo_description()
            self._redo_action.setText(f"Redo {desc}")
        else:
            self._redo_action.setText("Redo")

    def _on_undo_action_performed(self, message: str):
        """Show undo/redo result in status bar."""
        self._status_bar.showMessage(message)
        self._refresh()
