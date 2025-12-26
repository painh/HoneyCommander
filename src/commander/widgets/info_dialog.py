"""File/folder info dialog."""

import sys
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFormLayout,
    QPushButton,
    QGroupBox,
)


class InfoDialog(QDialog):
    """Dialog showing file/folder information."""

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self._path = path
        self._setup_ui()
        self.setWindowTitle(f"Info - {path.name}")
        self.setMinimumWidth(350)

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)

        # Icon and name
        header_layout = QHBoxLayout()

        icon_label = QLabel()
        icon = self.style().standardIcon(
            self.style().StandardPixmap.SP_DirIcon
            if self._path.is_dir()
            else self.style().StandardPixmap.SP_FileIcon
        )
        icon_label.setPixmap(icon.pixmap(48, 48))
        header_layout.addWidget(icon_label)

        name_label = QLabel(f"<b>{self._path.name}</b>")
        name_label.setWordWrap(True)
        header_layout.addWidget(name_label, stretch=1)

        layout.addLayout(header_layout)

        # General info
        general_group = QGroupBox("General")
        general_layout = QFormLayout(general_group)

        # Type
        if self._path.is_dir():
            type_str = "Folder"
        else:
            type_str = self._path.suffix.upper()[1:] + " File" if self._path.suffix else "File"
        general_layout.addRow("Type:", QLabel(type_str))

        # Location
        location_label = QLabel(str(self._path.parent))
        location_label.setWordWrap(True)
        location_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        general_layout.addRow("Location:", location_label)

        # Size
        try:
            if self._path.is_file():
                size = self._path.stat().st_size
                size_str = self._format_size(size)
            else:
                size_str = self._calculate_folder_size()
        except OSError:
            size_str = "Unknown"
        general_layout.addRow("Size:", QLabel(size_str))

        layout.addWidget(general_group)

        # Dates
        dates_group = QGroupBox("Dates")
        dates_layout = QFormLayout(dates_group)

        try:
            stat = self._path.stat()

            # Created
            if hasattr(stat, 'st_birthtime'):
                created = datetime.fromtimestamp(stat.st_birthtime)
            else:
                created = datetime.fromtimestamp(stat.st_ctime)
            dates_layout.addRow("Created:", QLabel(created.strftime("%Y-%m-%d %H:%M:%S")))

            # Modified
            modified = datetime.fromtimestamp(stat.st_mtime)
            dates_layout.addRow("Modified:", QLabel(modified.strftime("%Y-%m-%d %H:%M:%S")))

            # Accessed
            accessed = datetime.fromtimestamp(stat.st_atime)
            dates_layout.addRow("Accessed:", QLabel(accessed.strftime("%Y-%m-%d %H:%M:%S")))

        except OSError:
            dates_layout.addRow("", QLabel("Unable to read dates"))

        layout.addWidget(dates_group)

        # Permissions (Unix)
        if sys.platform != "win32":
            perms_group = QGroupBox("Permissions")
            perms_layout = QFormLayout(perms_group)

            try:
                import stat as stat_module
                mode = self._path.stat().st_mode

                perms = ""
                perms += "r" if mode & stat_module.S_IRUSR else "-"
                perms += "w" if mode & stat_module.S_IWUSR else "-"
                perms += "x" if mode & stat_module.S_IXUSR else "-"
                perms += " / "
                perms += "r" if mode & stat_module.S_IRGRP else "-"
                perms += "w" if mode & stat_module.S_IWGRP else "-"
                perms += "x" if mode & stat_module.S_IXGRP else "-"
                perms += " / "
                perms += "r" if mode & stat_module.S_IROTH else "-"
                perms += "w" if mode & stat_module.S_IWOTH else "-"
                perms += "x" if mode & stat_module.S_IXOTH else "-"

                perms_layout.addRow("Mode:", QLabel(f"{oct(mode)[-3:]} ({perms})"))

            except OSError:
                perms_layout.addRow("", QLabel("Unable to read permissions"))

            layout.addWidget(perms_group)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _calculate_folder_size(self) -> str:
        """Calculate folder size (may be slow for large folders)."""
        try:
            total = 0
            file_count = 0
            dir_count = 0

            for item in self._path.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
                    file_count += 1
                elif item.is_dir():
                    dir_count += 1

            size_str = self._format_size(total)
            return f"{size_str} ({file_count} files, {dir_count} folders)"
        except OSError:
            return "Unable to calculate"
