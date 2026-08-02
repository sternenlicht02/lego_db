"""Internationalization: language selection, persistence, and translation lookup."""

from __future__ import annotations

from lego_db.i18n.service import (
    LANGUAGE_LABELS,
    language_options_from_files,
    load_config,
    set_language,
    t,
    write_config,
)

__all__ = [
    "t",
    "set_language",
    "load_config",
    "write_config",
    "language_options_from_files",
    "LANGUAGE_LABELS",
]
