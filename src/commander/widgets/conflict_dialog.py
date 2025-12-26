"""Conflict resolution dialog for duplicate files."""

from pathlib import Path
from enum import Enum
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QGridLayout,
    QFrame,
)


class ConflictResolution(Enum):
    """Resolution options for file conflicts."""

    SKIP = "skip"
    OVERWRITE = "overwrite"
    RENAME = "rename"  # Keep both (rename new file)
    CANCEL = "cancel"


class ConflictDialog(QDialog):
    """Dialog for resolving file conflicts during copy/move operations."""

    def __init__(
        self,
        conflicts: list[tuple[Path, Path]],  # (source, existing_dest)
        parent=None,
    ):
        super().__init__(parent)
        self._conflicts = conflicts
        self._resolution = ConflictResolution.SKIP
        self._apply_to_all = len(conflicts) > 1  # Auto-check if multiple conflicts

        self.setWindowTitle("File Conflict")
        self.setMinimumWidth(500)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        if len(self._conflicts) == 1:
            header = QLabel("A file with the same name already exists in the destination.")
        else:
            header = QLabel(
                f"<b>{len(self._conflicts)} files</b> with the same names already exist in the destination."
            )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Show first conflict details
        src, dst = self._conflicts[0]

        # File info comparison
        info_group = QGroupBox("File Information")
        info_layout = QGridLayout(info_group)
        info_layout.setColumnStretch(1, 1)
        info_layout.setColumnStretch(2, 1)

        # Headers
        info_layout.addWidget(QLabel("<b>Source</b>"), 0, 1)
        info_layout.addWidget(QLabel("<b>Destination</b>"), 0, 2)

        # File name
        info_layout.addWidget(QLabel("Name:"), 1, 0)
        info_layout.addWidget(QLabel(src.name), 1, 1)
        info_layout.addWidget(QLabel(dst.name), 1, 2)

        # Size
        info_layout.addWidget(QLabel("Size:"), 2, 0)
        src_size = self._format_size(src.stat().st_size) if src.exists() else "N/A"
        dst_size = self._format_size(dst.stat().st_size) if dst.exists() else "N/A"
        info_layout.addWidget(QLabel(src_size), 2, 1)
        info_layout.addWidget(QLabel(dst_size), 2, 2)

        # Modified date
        info_layout.addWidget(QLabel("Modified:"), 3, 0)
        src_mtime = self._format_date(src.stat().st_mtime) if src.exists() else "N/A"
        dst_mtime = self._format_date(dst.stat().st_mtime) if dst.exists() else "N/A"
        info_layout.addWidget(QLabel(src_mtime), 3, 1)
        info_layout.addWidget(QLabel(dst_mtime), 3, 2)

        layout.addWidget(info_group)

        # Show "and X more files" if multiple conflicts
        if len(self._conflicts) > 1:
            more_label = QLabel(f"<i>...and {len(self._conflicts) - 1} more file(s)</i>")
            more_label.setStyleSheet("color: gray;")
            layout.addWidget(more_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Options
        options_label = QLabel("What would you like to do?")
        layout.addWidget(options_label)

        # Buttons for each option
        button_layout = QVBoxLayout()
        button_layout.setSpacing(8)

        # Overwrite
        self._overwrite_btn = QPushButton("Replace the file(s) in the destination")
        self._overwrite_btn.setStyleSheet("text-align: left; padding: 8px;")
        self._overwrite_btn.clicked.connect(lambda: self._resolve(ConflictResolution.OVERWRITE))
        button_layout.addWidget(self._overwrite_btn)

        # Skip
        self._skip_btn = QPushButton("Skip these file(s)")
        self._skip_btn.setStyleSheet("text-align: left; padding: 8px;")
        self._skip_btn.clicked.connect(lambda: self._resolve(ConflictResolution.SKIP))
        button_layout.addWidget(self._skip_btn)

        # Keep both (rename)
        self._rename_btn = QPushButton("Keep both (rename new file(s))")
        self._rename_btn.setStyleSheet("text-align: left; padding: 8px;")
        self._rename_btn.clicked.connect(lambda: self._resolve(ConflictResolution.RENAME))
        button_layout.addWidget(self._rename_btn)

        layout.addLayout(button_layout)

        # Bottom row with cancel
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(lambda: self._resolve(ConflictResolution.CANCEL))
        bottom_layout.addWidget(self._cancel_btn)

        layout.addLayout(bottom_layout)

    def _resolve(self, resolution: ConflictResolution) -> None:
        """Set resolution and close dialog."""
        self._resolution = resolution
        if resolution == ConflictResolution.CANCEL:
            self.reject()
        else:
            self.accept()

    def get_resolution(self) -> ConflictResolution:
        """Get the user's resolution choice."""
        return self._resolution

    def _format_size(self, size: int | float) -> str:
        """Format size in human-readable format."""
        size_f = float(size)
        for unit in ["B", "KB", "MB", "GB"]:
            if size_f < 1024:
                return f"{size_f:.1f} {unit}"
            size_f /= 1024
        return f"{size_f:.1f} TB"

    def _format_date(self, timestamp: float) -> str:
        """Format timestamp as date string."""
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
