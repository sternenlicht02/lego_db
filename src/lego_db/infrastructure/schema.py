"""Database schema for the catalog + owned-set inventory."""

from __future__ import annotations

from lego_db.infrastructure.database import Database

_SCHEMA = """
CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id INTEGER,
    FOREIGN KEY (parent_id) REFERENCES themes(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sets (
    set_num TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    year INTEGER,
    theme_id INTEGER,
    num_parts INTEGER,
    FOREIGN KEY (theme_id) REFERENCES themes(id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
);

-- added_at is an ISO date ("YYYY-MM-DD") recording when a set was added
-- to the owned list; it drives the export filename (see exporters.py)
-- and is otherwise not shown anywhere in the UI.
CREATE TABLE IF NOT EXISTS owned_sets (
    set_num TEXT PRIMARY KEY,
    condition INTEGER NOT NULL DEFAULT 0 CHECK (condition IN (0, 1, 2)),
    note TEXT,
    added_at TEXT NOT NULL,
    FOREIGN KEY (set_num) REFERENCES sets(set_num)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sets_theme_year ON sets(theme_id, year);
"""


def initialize_schema(db: Database) -> None:
    db.script(_SCHEMA)
