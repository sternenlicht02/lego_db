"""
Runtime path resolution.

The one module that knows where things live on disk: the CSV dataset
bundled with the package, the locale files, and the per-user runtime data
(database + exports + language choice). Nothing in domain or application
imports this; only infrastructure, presentation, and the top-level scripts
do.
"""

from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent


def project_root() -> Path:
    """The repository root (two levels above ``src/lego_db``)."""
    return _PACKAGE_DIR.parents[1]


def instance_dir() -> Path:
    """Per-user runtime data: the database and exported backups."""
    path = project_root() / "instance"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return instance_dir() / "lego_db.db"


def export_dir() -> Path:
    path = instance_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def csv_data_dir() -> Path:
    return _PACKAGE_DIR / "data" / "csv"


def locale_dir() -> Path:
    return _PACKAGE_DIR / "i18n" / "locales"


def config_path() -> Path:
    """
    Path to the language-selection config file.

    Kept at the repository root rather than under ``instance/`` so it's
    easy to find and edit by hand, matching where the original app put it.
    """
    return project_root() / "config.json"
