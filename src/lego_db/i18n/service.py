"""
Runtime i18n service.

On first launch, if ``config.json`` doesn't exist yet, the GUI shows a
language selection dialog and persists the choice here. Everything below
is plain JSON handling -- no external i18n library, per the project's
standard-library-only constraint.
"""

from __future__ import annotations

import json
from typing import Final

from lego_db.paths import config_path, locale_dir

LANGUAGE_LABELS: Final[dict[str, str]] = {
    "arz": "مصري عربي",
    "bn": "বাংলা",
    "cmn": "中文(普通话)",
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "hi": "हिन्दी",
    "id": "Bahasa Indonesia",
    "ja": "日本語",
    "ko": "한국어",
    "mr": "मराठी",
    "pt": "Português",
    "ru": "Русский",
    "ta": "தமிழ்",
    "te": "తెలుగు",
    "tr": "Türkçe",
    "ur": "اردو",
    "vi": "Tiếng Việt",
    "wuu": "吴语",
    "yue": "粵語",
}


def _build_language_comment() -> str:
    return ", ".join(f"[{code}]{LANGUAGE_LABELS[code]}" for code in sorted(LANGUAGE_LABELS))


_LANGUAGE_COMMENT: Final[str] = _build_language_comment()


def load_config() -> dict:
    try:
        with config_path().open(encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"language": "en"}


def write_config(language: str) -> None:
    data = {"_comment": _LANGUAGE_COMMENT, "language": language}
    config_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def language_options_from_files() -> list[tuple[str, str]]:
    """(code, display_label) pairs for every locale file present on disk."""
    directory = locale_dir()
    if not directory.exists():
        return []
    file_codes = {path.stem for path in directory.glob("*.json") if path.is_file()}
    return [(code, f"[{code}]{LANGUAGE_LABELS.get(code, code)}") for code in sorted(file_codes)]


class _Translator:
    def __init__(self, code: str) -> None:
        self.code = code
        self._strings: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        path = locale_dir() / f"{self.code}.json"
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                self._strings = data
                return
        except Exception:
            pass

        if self.code != "en":
            fallback = locale_dir() / "en.json"
            try:
                with fallback.open(encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    self._strings = data
                    return
            except Exception:
                pass

        self._strings = {}

    def t(self, key: str) -> str:
        return str(self._strings.get(key, key))


_active = _Translator("en")


def set_language(code: str) -> None:
    global _active
    _active = _Translator(code)


def t(key: str) -> str:
    return _active.t(key)
