"""Text viewer widget with syntax highlighting."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from PySide6.QtWidgets import QPlainTextEdit

from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.token import (
    Comment,
    Keyword,
    Name,
    String,
    Number,
    Operator,
    Punctuation,
    Error,
)


# Token to color mapping (dark theme friendly)
TOKEN_COLORS = {
    Comment: "#6A9955",
    Comment.Single: "#6A9955",
    Comment.Multiline: "#6A9955",
    Comment.Preproc: "#C586C0",
    Keyword: "#569CD6",
    Keyword.Constant: "#569CD6",
    Keyword.Declaration: "#569CD6",
    Keyword.Namespace: "#C586C0",
    Keyword.Type: "#4EC9B0",
    Name.Builtin: "#DCDCAA",
    Name.Function: "#DCDCAA",
    Name.Class: "#4EC9B0",
    Name.Decorator: "#DCDCAA",
    Name.Exception: "#4EC9B0",
    Name.Variable: "#9CDCFE",
    Name.Attribute: "#9CDCFE",
    Name.Tag: "#569CD6",
    String: "#CE9178",
    String.Doc: "#6A9955",
    String.Escape: "#D7BA7D",
    String.Regex: "#D16969",
    Number: "#B5CEA8",
    Number.Integer: "#B5CEA8",
    Number.Float: "#B5CEA8",
    Number.Hex: "#B5CEA8",
    Operator: "#D4D4D4",
    Operator.Word: "#569CD6",
    Punctuation: "#D4D4D4",
    Error: "#F44747",
}


class PygmentsHighlighter(QSyntaxHighlighter):
    """Syntax highlighter using Pygments."""

    def __init__(self, document: QTextDocument, lexer=None):
        super().__init__(document)
        self._lexer = lexer or TextLexer()
        self._formats: dict = {}
        self._build_formats()

    def _build_formats(self):
        """Build QTextCharFormat for each token type."""
        for token_type, color in TOKEN_COLORS.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if token_type in (Keyword, Keyword.Constant, Keyword.Declaration):
                fmt.setFontWeight(QFont.Weight.Bold)
            self._formats[token_type] = fmt

    def set_lexer(self, lexer):
        """Set the lexer to use."""
        self._lexer = lexer
        self.rehighlight()

    def highlightBlock(self, text: str):
        """Highlight a block of text."""
        if not text:
            return

        try:
            tokens = self._lexer.get_tokens(text)
            index = 0
            for token_type, value in tokens:
                length = len(value)
                if length == 0:
                    continue

                # Find matching format
                fmt = self._get_format(token_type)
                if fmt:
                    self.setFormat(index, length, fmt)
                index += length
        except Exception:
            pass  # Fail silently on highlighting errors

    def _get_format(self, token_type) -> QTextCharFormat | None:
        """Get format for token type, checking parent types."""
        while token_type:
            if token_type in self._formats:
                return self._formats[token_type]
            # Try parent token type
            token_type = token_type.parent
        return None


class TextViewer(QPlainTextEdit):
    """Text viewer/editor with syntax highlighting."""

    content_modified = Signal(bool)

    # Text file extensions
    TEXT_EXTENSIONS = {
        # Code
        ".py",
        ".pyw",
        ".pyi",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cc",
        ".hh",
        ".cxx",
        ".java",
        ".kt",
        ".kts",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".cs",
        ".fs",
        ".vb",
        ".swift",
        ".m",
        ".mm",
        ".r",
        ".R",
        ".pl",
        ".pm",
        ".perl",
        ".lua",
        ".tcl",
        ".scala",
        ".clj",
        ".cljs",
        ".hs",
        ".elm",
        ".erl",
        ".ex",
        ".exs",
        ".v",
        ".sv",
        ".asm",
        ".s",
        # Web
        ".html",
        ".htm",
        ".xhtml",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".vue",
        ".svelte",
        # Data/Config
        ".json",
        ".jsonc",
        ".json5",
        ".yaml",
        ".yml",
        ".xml",
        ".xsl",
        ".xslt",
        ".xsd",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".properties",
        ".csv",
        ".tsv",
        # Shell/Script
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".ps1",
        ".psm1",
        ".psd1",
        ".bat",
        ".cmd",
        # Documentation
        ".txt",
        ".text",
        ".md",
        ".markdown",
        ".rst",
        ".asciidoc",
        ".tex",
        ".latex",
        # Other
        ".sql",
        ".graphql",
        ".gql",
        ".dockerfile",
        ".containerfile",
        ".makefile",
        ".mk",
        ".cmake",
        ".gradle",
        ".sbt",
        ".tf",
        ".tfvars",
        ".vim",
        ".vimrc",
        ".gitignore",
        ".gitattributes",
        ".gitmodules",
        ".editorconfig",
        ".log",
    }

    # Special filenames (no extension)
    TEXT_FILENAMES = {
        "Makefile",
        "makefile",
        "GNUmakefile",
        "Dockerfile",
        "Containerfile",
        "Vagrantfile",
        "Gemfile",
        "Rakefile",
        "CMakeLists.txt",
        "README",
        "LICENSE",
        "CHANGELOG",
        "HISTORY",
        "AUTHORS",
        "CONTRIBUTORS",
        "COPYING",
        "INSTALL",
        "TODO",
        "NEWS",
        ".gitignore",
        ".gitattributes",
        ".gitmodules",
        ".dockerignore",
        ".editorconfig",
        ".bashrc",
        ".bash_profile",
        ".zshrc",
        ".profile",
        ".vimrc",
        ".gvimrc",
    }

    MAX_FILE_SIZE = 50 * 1024  # 50KB

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path: Path | None = None
        self._original_content: str = ""
        self._highlighter: PygmentsHighlighter | None = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the text editor UI."""
        # Monospace font
        font = QFont("Menlo, Monaco, Consolas, 'Courier New', monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(12)
        self.setFont(font)

        # Tab width
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)

        # Line wrap
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Enable context menu with copy/paste
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        # Track modifications
        self.textChanged.connect(self._on_text_changed)

        # Create highlighter
        self._highlighter = PygmentsHighlighter(self.document())

    def _on_text_changed(self):
        """Handle text changes."""
        is_modified = self.toPlainText() != self._original_content
        self.content_modified.emit(is_modified)

    @classmethod
    def is_text_file(cls, path: Path) -> bool:
        """Check if path is a text file we can display."""
        if not path.is_file():
            return False

        # Check by filename
        if path.name in cls.TEXT_FILENAMES:
            return True

        # Check by extension
        suffix = path.suffix.lower()
        if suffix in cls.TEXT_EXTENSIONS:
            return True

        # Check if no extension but looks like text
        if not suffix:
            # Try to detect if it's a text file
            try:
                with open(path, "rb") as f:
                    chunk = f.read(1024)
                    # Check for null bytes (binary indicator)
                    if b"\x00" in chunk:
                        return False
                    # Try to decode as UTF-8
                    try:
                        chunk.decode("utf-8")
                        return True
                    except UnicodeDecodeError:
                        return False
            except (OSError, IOError):
                return False

        return False

    @classmethod
    def get_file_size(cls, path: Path) -> int:
        """Get file size in bytes."""
        try:
            return path.stat().st_size
        except OSError:
            return 0

    @classmethod
    def is_too_large(cls, path: Path) -> bool:
        """Check if file is too large to display."""
        return cls.get_file_size(path) > cls.MAX_FILE_SIZE

    def load_file(self, path: Path) -> bool:
        """Load a text file. Returns True on success."""
        self._current_path = path

        try:
            # Try different encodings
            content = None
            for encoding in ["utf-8", "utf-8-sig", "cp949", "euc-kr", "latin-1"]:
                try:
                    with open(path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                self.setPlainText("Cannot decode file content")
                return False

            self._original_content = content
            self.setPlainText(content)

            # Set lexer based on file type
            self._set_lexer_for_file(path)

            return True

        except Exception as e:
            self.setPlainText(f"Error loading file: {e}")
            return False

    def _set_lexer_for_file(self, path: Path):
        """Set appropriate lexer for the file."""
        try:
            lexer = get_lexer_for_filename(path.name)
        except Exception:
            lexer = TextLexer()

        if self._highlighter:
            self._highlighter.set_lexer(lexer)

    def save_file(self) -> bool:
        """Save the current file. Returns True on success."""
        if not self._current_path:
            return False

        try:
            with open(self._current_path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())
            self._original_content = self.toPlainText()
            self.content_modified.emit(False)
            return True
        except Exception:
            return False

    def is_modified(self) -> bool:
        """Check if content has been modified."""
        return self.toPlainText() != self._original_content

    def get_current_path(self) -> Path | None:
        """Get the currently loaded file path."""
        return self._current_path
