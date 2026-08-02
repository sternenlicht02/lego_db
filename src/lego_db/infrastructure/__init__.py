"""
Infrastructure layer.

SQLite access, schema management, CSV import, and owned-set export/import.
This is the only layer that imports sqlite3 or csv.
"""

from __future__ import annotations

from lego_db.infrastructure.database import Database
from lego_db.infrastructure.repositories import SQLiteCatalogRepository, SQLiteOwnedRepository
from lego_db.infrastructure.schema import initialize_schema

__all__ = [
    "Database",
    "initialize_schema",
    "SQLiteCatalogRepository",
    "SQLiteOwnedRepository",
]
