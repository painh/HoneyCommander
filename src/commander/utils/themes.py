"""Theme system for file type colors."""

from dataclasses import dataclass, field
from pathlib import Path

from commander.utils.settings import Settings


@dataclass
class ColorTheme:
    """Color theme definition."""

    name: str
    display_name: str
    description: str
    colors: dict[str, str | None] = field(default_factory=dict)
    extensions: dict[str, set[str]] = field(default_factory=dict)
    special_files: set[str] = field(default_factory=set)


# === Theme Definitions ===

# No colors (system default)
THEME_NONE = ColorTheme(
    name="none",
    display_name="None (System Default)",
    description="Use system default colors",
    colors={},
    extensions={},
    special_files=set(),
)

# MDIR.js / Retro Commander style
THEME_RETRO = ColorTheme(
    name="retro",
    display_name="Retro Commander (MDIR)",
    description="Classic MDIR.js style colors from the DOS era",
    colors={
        # Directories - Orange (9 in MDIR)
        "directory": "#FFA500",
        # Archives - Pink/Magenta (13 in MDIR)
        "archive": "#FF55FF",
        # Documents - Sky Blue (12 in MDIR)
        "document": "#55AAFF",
        # Executables/Libraries - Violet (5 in MDIR)
        "executable": "#AA55FF",
        # Images - Dark Green (2 in MDIR, like ICO files)
        "image": "#008800",
        # Media (audio/video) - Brown/Dark Yellow (3 in MDIR)
        "media": "#CDCD00",
        # Text/Config/Code - Cyan (6 in MDIR)
        "code": "#55FFFF",
        # Headers/JSON/Shell - Light Green (10 in MDIR)
        "header": "#90EE90",
        # Special files (Makefile etc) - Light Blue (14 in MDIR)
        "special": "#ADD8E6",
    },
    extensions={
        "archive": {
            ".tar",
            ".bz2",
            ".tbz",
            ".tgz",
            ".gz",
            ".zip",
            ".z",
            ".rpm",
            ".deb",
            ".alz",
            ".jar",
            ".iso",
            ".rar",
            ".lzh",
            ".cab",
            ".arj",
            ".xz",
            ".txz",
            ".7z",
            ".lz",
            ".lzma",
            ".dmg",
            ".pkg",
            ".apk",
            ".war",
        },
        "document": {
            ".xls",
            ".xlw",
            ".xlt",
            ".lwp",
            ".wps",
            ".ods",
            ".ots",
            ".sxc",
            ".stc",
            ".csv",
            ".hwp",
            ".hwpx",
            ".pdf",
            ".doc",
            ".docx",
            ".dot",
            ".rtf",
            ".sdw",
            ".vor",
            ".pdb",
            ".odt",
            ".psw",
            ".pwd",
            ".jtd",
            ".jtt",
            ".dif",
            ".dbf",
            ".ott",
            ".sxw",
            ".odg",
            ".odp",
            ".ppt",
            ".pptx",
            ".xlsx",
            ".pem",
            ".cer",
            ".p7b",
            ".der",
            ".epub",
            ".tex",
        },
        "executable": {
            ".exe",
            ".com",
            ".bat",
            ".cmd",
            ".msi",
            ".a",
            ".so",
            ".la",
            ".dll",
            ".dylib",
            ".app",
            ".bin",
            ".run",
            ".appimage",
        },
        "image": {
            ".bmp",
            ".tga",
            ".pcx",
            ".gif",
            ".jpg",
            ".jpeg",
            ".png",
            ".pbm",
            ".pgm",
            ".ppm",
            ".xbm",
            ".xpm",
            ".ico",
            ".svg",
            ".webp",
            ".tiff",
            ".tif",
            ".psd",
            ".psb",
            ".raw",
            ".cr2",
            ".nef",
            ".heic",
            ".avif",
        },
        "media": {
            ".mp2",
            ".mp3",
            ".wav",
            ".aiff",
            ".voc",
            ".ogg",
            ".flac",
            ".aac",
            ".wma",
            ".m4a",
            ".opus",
            ".avi",
            ".mpg",
            ".mov",
            ".asf",
            ".mpeg",
            ".wmv",
            ".mp4",
            ".mkv",
            ".divx",
            ".rm",
            ".amv",
            ".flv",
            ".webm",
            ".m4v",
            ".3gp",
        },
        "code": {
            ".txt",
            ".md",
            ".me",
            ".ini",
            ".cfg",
            ".log",
            ".am",
            ".in",
            ".conf",
            ".m4",
            ".po",
            ".spec",
            ".html",
            ".htm",
            ".xml",
            ".css",
            ".js",
            ".jsp",
            ".php",
            ".php3",
            ".asp",
            ".jsx",
            ".ts",
            ".tsx",
            ".c",
            ".cpp",
            ".cc",
            ".pl",
            ".java",
            ".py",
            ".diff",
            ".diff3",
            ".rb",
            ".go",
            ".rs",
            ".kt",
            ".swift",
            ".cs",
            ".scss",
            ".sass",
            ".less",
            ".yaml",
            ".yml",
            ".toml",
            ".sql",
            ".ps1",
            ".vue",
            ".svelte",
        },
        "header": {
            ".h",
            ".hh",
            ".hpp",
            ".json",
            ".sh",
            ".bash",
            ".zsh",
            ".fish",
        },
    },
    special_files={
        "Makefile",
        "makefile",
        "CMakeLists.txt",
        "Dockerfile",
        "Vagrantfile",
        "README",
        "README.md",
        "NEWS",
        "COPYING",
        "AUTHORS",
        "INSTALL",
        "TODO",
        "ChangeLog",
        "Doxyfile",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "requirements.txt",
        ".gitignore",
        ".dockerignore",
        ".editorconfig",
    },
)

# Modern Dark theme
THEME_MODERN_DARK = ColorTheme(
    name="modern_dark",
    display_name="Modern Dark",
    description="Modern color scheme optimized for dark backgrounds",
    colors={
        "directory": "#569CD6",  # Blue
        "archive": "#C586C0",  # Purple/Pink
        "document": "#4EC9B0",  # Teal
        "executable": "#DCDCAA",  # Yellow
        "image": "#6A9955",  # Green
        "media": "#CE9178",  # Orange/Brown
        "code": "#9CDCFE",  # Light Blue
        "header": "#4FC1FF",  # Bright Blue
        "special": "#D7BA7D",  # Gold
    },
    extensions=THEME_RETRO.extensions,  # Reuse same extensions
    special_files=THEME_RETRO.special_files,
)

# Modern Light theme
THEME_MODERN_LIGHT = ColorTheme(
    name="modern_light",
    display_name="Modern Light",
    description="Modern color scheme optimized for light backgrounds",
    colors={
        "directory": "#0000FF",  # Blue
        "archive": "#AF00DB",  # Purple
        "document": "#008080",  # Teal
        "executable": "#795E26",  # Brown
        "image": "#008000",  # Green
        "media": "#A31515",  # Dark Red
        "code": "#0070C1",  # Blue
        "header": "#267F99",  # Cyan
        "special": "#E36209",  # Orange
    },
    extensions=THEME_RETRO.extensions,
    special_files=THEME_RETRO.special_files,
)

# All available themes
THEMES: dict[str, ColorTheme] = {
    "none": THEME_NONE,
    "retro": THEME_RETRO,
    "modern_dark": THEME_MODERN_DARK,
    "modern_light": THEME_MODERN_LIGHT,
}

# Default theme
DEFAULT_THEME = "retro"


class ThemeManager:
    """Manages color themes."""

    _instance: "ThemeManager | None" = None

    def __init__(self):
        self._settings = Settings()
        self._current_theme: ColorTheme | None = None

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_current_theme(self) -> ColorTheme:
        """Get current theme."""
        if self._current_theme is None:
            theme_name = self._settings.load_color_theme()
            self._current_theme = THEMES.get(theme_name, THEMES[DEFAULT_THEME])
        return self._current_theme

    def set_theme(self, theme_name: str) -> None:
        """Set current theme."""
        if theme_name in THEMES:
            self._settings.save_color_theme(theme_name)
            self._current_theme = THEMES[theme_name]

    def get_available_themes(self) -> list[ColorTheme]:
        """Get list of available themes."""
        return list(THEMES.values())

    def get_file_color(self, path: Path) -> str | None:
        """Get color for file based on current theme."""
        theme = self.get_current_theme()

        if not theme.colors:
            return None  # No colors theme

        if path.is_dir():
            return theme.colors.get("directory")

        name = path.name
        suffix = path.suffix.lower()

        # Check special filenames first
        if name in theme.special_files:
            return theme.colors.get("special")

        # Check by extension
        for file_type, extensions in theme.extensions.items():
            if suffix in extensions:
                return theme.colors.get(file_type)

        return None  # Default color


def get_theme_manager() -> ThemeManager:
    """Get singleton ThemeManager instance."""
    return ThemeManager.instance()


def get_file_color(path: Path) -> str | None:
    """Convenience function to get file color from current theme."""
    return get_theme_manager().get_file_color(path)
