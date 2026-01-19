"""Fuzzy search mixin for file list view."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QModelIndex


class FileListSearchMixin:
    """Mixin providing fuzzy search functionality."""

    # Expected from main class
    _current_path: Path | None
    _search_text: str
    _search_label: object
    _search_timer: object
    _model: object

    def eventFilter(self, obj, event) -> bool:
        """Filter key events from child views for fuzzy search and custom commands."""
        # Handle focus events from child views
        if event.type() in (event.Type.FocusIn, event.Type.FocusOut):
            self._update_focus_style()

        if event.type() == event.Type.KeyPress:
            key = event.key()
            text = event.text()

            # Escape clears search
            if key == Qt.Key.Key_Escape and self._search_text:
                self._clear_search()
                return True

            # Backspace removes last character from search
            if key == Qt.Key.Key_Backspace and self._search_text:
                self._search_text = self._search_text[:-1]
                if self._search_text:
                    self._do_fuzzy_search()
                else:
                    self._clear_search()
                return True

            # Only handle printable characters (no modifiers except shift)
            modifiers = event.modifiers()
            has_ctrl_or_meta = modifiers & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
            )

            if text and text.isprintable() and not has_ctrl_or_meta:
                # Check for custom command shortcut first (only when not searching)
                if not self._search_text:
                    if self._try_custom_command_shortcut(text.upper()):
                        return True

                self._search_text += text.lower()
                self._do_fuzzy_search()
                self._search_timer.start()
                return True

        return super().eventFilter(obj, event)

    def _try_custom_command_shortcut(self, shortcut: str) -> bool:
        """Try to execute custom command by shortcut. Returns True if handled."""
        from commander.utils.custom_commands import get_custom_commands_manager

        selected_paths = self.get_selected_paths()
        if not selected_paths:
            return False

        path = selected_paths[0]
        mgr = get_custom_commands_manager()

        for cmd in mgr.get_commands_for_path(path):
            if cmd.shortcut and cmd.shortcut.upper() == shortcut:
                self._run_custom_command(cmd, path)
                return True

        return False

    def _do_fuzzy_search(self) -> None:
        """Perform fuzzy search and select matching file."""
        if not self._search_text or not self._current_path:
            return

        # Show search overlay
        self._search_label.setText(f"Search: {self._search_text}")
        self._search_label.adjustSize()
        self._search_label.move(10, self.height() - self._search_label.height() - 10)
        self._search_label.show()

        # Get all items in current directory
        view = self._current_view()
        model = self._model
        root_index = view.rootIndex()

        best_match: QModelIndex | None = None
        best_score = -1

        for row in range(model.rowCount(root_index)):
            index = model.index(row, 0, root_index)
            filename = model.fileName(index).lower()

            # Calculate fuzzy match score
            score = self._fuzzy_score(self._search_text, filename)
            if score > best_score:
                best_score = score
                best_match = index

        # Select best match
        if best_match is not None and best_score > 0:
            view.setCurrentIndex(best_match)
            view.scrollTo(best_match)
            self._on_clicked(best_match)

    def _fuzzy_score(self, pattern: str, text: str) -> int:
        """Calculate fuzzy match score. Higher is better."""
        if not pattern:
            return 0

        # Exact prefix match gets highest score
        if text.startswith(pattern):
            return 1000 + len(pattern)

        # Check if all characters appear in order
        pattern_idx = 0
        score = 0
        consecutive = 0

        for i, char in enumerate(text):
            if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
                pattern_idx += 1
                consecutive += 1
                # Bonus for consecutive matches
                score += consecutive * 10
                # Bonus for match at start
                if i == 0:
                    score += 50
            else:
                consecutive = 0

        # All pattern characters must be found
        if pattern_idx < len(pattern):
            return 0

        return score

    def _clear_search(self) -> None:
        """Clear fuzzy search."""
        self._search_text = ""
        self._search_label.hide()
        self._search_timer.stop()

    def handle_backspace(self) -> bool:
        """Handle backspace key for search. Returns True if handled."""
        if self._search_text:
            self._search_text = self._search_text[:-1]
            if self._search_text:
                self._do_fuzzy_search()
            else:
                self._clear_search()
            return True
        return False

    def has_search_text(self) -> bool:
        """Check if there is active search text."""
        return bool(self._search_text)
