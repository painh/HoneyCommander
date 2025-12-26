"""Keyboard shortcuts dialog."""

import sys
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QWidget,
    QPushButton,
    QFrame,
)

from commander.utils.i18n import tr


def _mod() -> str:
    """Return platform-specific modifier key."""
    return "⌘" if sys.platform == "darwin" else "Ctrl"


def _alt() -> str:
    """Return platform-specific alt key."""
    return "⌥" if sys.platform == "darwin" else "Alt"


def _del() -> str:
    """Return platform-specific delete key."""
    return "⌫" if sys.platform == "darwin" else "Delete"


class ShortcutsDialog(QDialog):
    """Dialog showing all keyboard shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("shortcuts"))
        self.setMinimumSize(600, 500)
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)

        # Scroll area for shortcuts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)

        mod = _mod()
        alt = _alt()
        delete = _del()

        # File Explorer shortcuts
        self._add_section(
            content_layout,
            tr("shortcut_section_navigation"),
            [
                (f"{mod}+L", tr("shortcut_focus_address")),
                ("F3", tr("shortcut_search")),
                ("F5", tr("shortcut_refresh")),
                ("⌫" if sys.platform == "darwin" else "Backspace", tr("shortcut_go_up")),
                (f"{mod}+↑", tr("shortcut_go_up")),
                (f"{mod}+↓", tr("shortcut_open_item")),
                (f"{alt}+←", tr("shortcut_go_back")),
                (f"{alt}+→", tr("shortcut_go_forward")),
            ],
        )

        self._add_section(
            content_layout,
            tr("shortcut_section_file_ops"),
            [
                (f"{mod}+C", tr("copy")),
                (f"{mod}+X", tr("cut")),
                (f"{mod}+V", tr("paste")),
                (delete, tr("delete")),
                ("F2", tr("rename")),
                (f"{mod}+⇧+N", tr("new_folder")),
                (f"{mod}+Z", tr("undo")),
                (f"{mod}+⇧+Z", tr("redo")),
            ],
        )

        # Image Viewer shortcuts
        self._add_section(
            content_layout,
            tr("shortcut_section_viewer_nav"),
            [
                (
                    "←, ⌫, PageUp" if sys.platform == "darwin" else "←, Backspace, PageUp",
                    tr("prev_image"),
                ),
                ("→, Space, PageDown", tr("next_image")),
                ("[", tr("prev_folder")),
                ("]", tr("next_folder")),
                ("Home", tr("shortcut_first_image")),
                ("End", tr("shortcut_last_image")),
                (tr("shortcut_mouse_wheel"), tr("shortcut_prev_next")),
            ],
        )

        self._add_section(
            content_layout,
            tr("shortcut_section_viewer_zoom"),
            [
                ("0, 1", tr("original_size")),
                ("9", tr("fit_to_screen")),
                ("+, =", tr("zoom_in")),
                ("-", tr("zoom_out")),
                (tr("shortcut_middle_click"), tr("fit_to_screen")),
            ],
        )

        self._add_section(
            content_layout,
            tr("shortcut_section_viewer_transform"),
            [
                ("R", tr("rotate_cw")),
                ("⇧+R", tr("rotate_ccw")),
                ("H", tr("flip_h")),
                ("V", tr("flip_v")),
                ("U", tr("shortcut_filter_off")),
                ("S", tr("shortcut_filter_smooth")),
            ],
        )

        self._add_section(
            content_layout,
            tr("shortcut_section_viewer_file"),
            [
                ("F2", tr("shortcut_open_file")),
                ("F", tr("shortcut_open_folder")),
                ("F4, Esc, X", tr("shortcut_close_viewer")),
                ("Enter ↩" if sys.platform == "darwin" else "Enter", tr("shortcut_select_image")),
                (
                    f"{mod}+↩" if sys.platform == "darwin" else f"{mod}+Enter",
                    tr("shortcut_open_in_explorer"),
                ),
                ("Tab ⇥", tr("file_info")),
                (delete, tr("delete_file")),
                (f"{mod}+C", tr("shortcut_copy_clipboard")),
                (f"{mod}+E", tr("shortcut_open_editor")),
                ("Insert", tr("copy_to_photos") + " (macOS)"),
            ],
        )

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton(tr("ok"))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _add_section(self, layout: QVBoxLayout, title: str, shortcuts: list[tuple[str, str]]):
        """Add a section of shortcuts."""
        # Section title
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("font-size: 14px; margin-top: 10px;")
        layout.addWidget(title_label)

        # Shortcuts grid
        grid = QWidget()
        grid_layout = QVBoxLayout(grid)
        grid_layout.setSpacing(4)
        grid_layout.setContentsMargins(10, 5, 0, 0)

        for key, desc in shortcuts:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            key_label = QLabel(f"<code>{key}</code>")
            key_label.setFixedWidth(180)
            key_label.setStyleSheet("color: #0066cc; font-weight: bold;")

            desc_label = QLabel(desc)
            desc_label.setWordWrap(True)

            row_layout.addWidget(key_label)
            row_layout.addWidget(desc_label, stretch=1)
            grid_layout.addWidget(row)

        layout.addWidget(grid)
