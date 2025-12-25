"""Internationalization support."""

import json
import locale
import sys
from pathlib import Path
from typing import Dict


class I18n:
    """Internationalization manager."""

    _instance = None
    _language = "en"
    _translations: Dict[str, str] = {}

    SUPPORTED_LANGUAGES = ["en", "ko", "ja", "zh_CN", "zh_TW", "es"]

    # Language display names
    LANGUAGE_NAMES = {
        "en": "English",
        "ko": "한국어",
        "ja": "日本語",
        "zh_CN": "简体中文",
        "zh_TW": "繁體中文",
        "es": "Español",
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_language()
        return cls._instance

    def _get_locales_dir(self) -> Path:
        """Get the locales directory path."""
        # Try relative to this file first
        locales_dir = Path(__file__).parent.parent / "locales"
        if locales_dir.exists():
            return locales_dir

        # Fallback for frozen apps (PyInstaller)
        if getattr(sys, 'frozen', False):
            locales_dir = Path(sys._MEIPASS) / "commander" / "locales"
            if locales_dir.exists():
                return locales_dir

        return locales_dir

    def _load_translations(self):
        """Load translations from JSON file for current language."""
        locales_dir = self._get_locales_dir()
        lang_file = locales_dir / f"{self._language}.json"

        # Load target language
        if lang_file.exists():
            try:
                with open(lang_file, "r", encoding="utf-8") as f:
                    self._translations = json.load(f)
                return
            except (json.JSONDecodeError, IOError):
                pass

        # Fallback to English
        en_file = locales_dir / "en.json"
        if en_file.exists():
            try:
                with open(en_file, "r", encoding="utf-8") as f:
                    self._translations = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._translations = {}

    def _load_language(self):
        """Load language from settings or detect from system."""
        from commander.utils.settings import Settings
        settings = Settings()
        saved_lang = settings.load_language()
        if saved_lang and saved_lang in self.SUPPORTED_LANGUAGES:
            self._language = saved_lang
        else:
            self._detect_language()

        self._load_translations()

    def _detect_language(self):
        """Detect system language."""
        try:
            if sys.platform == "darwin":
                # macOS: use defaults command
                import subprocess
                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleLanguages"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    # Parse output like "(\n    ko,\n    en\n)"
                    output = result.stdout
                    for lang in self.SUPPORTED_LANGUAGES:
                        if lang.lower() in output.lower() or lang.replace("_", "-").lower() in output.lower():
                            self._language = lang
                            return
                    # Check for language variants
                    if "zh-hans" in output.lower() or "zh-cn" in output.lower():
                        self._language = "zh_CN"
                        return
                    if "zh-hant" in output.lower() or "zh-tw" in output.lower():
                        self._language = "zh_TW"
                        return

            # Fallback: use locale
            lang_code = locale.getdefaultlocale()[0]
            if lang_code:
                lang = lang_code.split("_")[0].lower()
                if lang == "ko":
                    self._language = "ko"
                elif lang == "ja":
                    self._language = "ja"
                elif lang == "zh":
                    # Differentiate simplified vs traditional
                    if "tw" in lang_code.lower() or "hant" in lang_code.lower():
                        self._language = "zh_TW"
                    else:
                        self._language = "zh_CN"
                elif lang == "es":
                    self._language = "es"
                else:
                    self._language = "en"
        except Exception:
            self._language = "en"

    @property
    def language(self) -> str:
        """Get current language."""
        return self._language

    @language.setter
    def language(self, lang: str):
        """Set language manually."""
        if lang in self.SUPPORTED_LANGUAGES:
            self._language = lang
            self._load_translations()

    def get(self, key: str, **kwargs) -> str:
        """Get translated string."""
        text = self._translations.get(key, key)

        # Format with kwargs
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass

        return text


# Global instance
_i18n: I18n | None = None


def get_i18n() -> I18n:
    """Get the global I18n instance."""
    global _i18n
    if _i18n is None:
        _i18n = I18n()
    return _i18n


def tr(key: str, **kwargs) -> str:
    """Translate a key. Shortcut for get_i18n().get(key)."""
    return get_i18n().get(key, **kwargs)
