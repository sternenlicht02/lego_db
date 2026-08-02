"""
SQLite implementations of the ``CatalogRepository`` and ``OwnedRepository``
ports.

Both read sides join ``sets`` + ``themes`` (twice, for the theme and its
parent theme) + ``owned_sets`` in a single query and share the same row
column list, rather than fetching catalog data and ownership data
separately and stitching them together in Python -- for a local SQLite
file the join is effectively free, and it keeps a "search" or "list owned"
call down to exactly one round trip regardless of how many rows come back.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Callable, Iterator, Optional, TypeVar

from lego_db.application.catalog_row import CatalogRow
from lego_db.domain.value_objects import Condition, SetNumber
from lego_db.infrastructure.database import Database

_T = TypeVar("_T")

_ROW_COLUMNS_SQL = """
    s.set_num AS set_num,
    COALESCE(pt.name, '') AS parent_theme,
    COALESCE(t.name, '') AS theme,
    s.name AS name,
    s.num_parts AS num_parts,
    s.year AS year,
    o.condition AS condition,
    COALESCE(o.note, '') AS note
"""

# Starting from `sets`: every catalog set, owned or not (LEFT JOIN owned_sets).
_CATALOG_FROM_SQL = """
    FROM sets s
    LEFT JOIN themes t ON s.theme_id = t.id
    LEFT JOIN themes pt ON t.parent_id = pt.id
    LEFT JOIN owned_sets o ON o.set_num = s.set_num
"""

# Starting from `owned_sets`: only sets the user owns.
_OWNED_FROM_SQL = """
    FROM owned_sets o
    JOIN sets s ON o.set_num = s.set_num
    LEFT JOIN themes t ON s.theme_id = t.id
    LEFT JOIN themes pt ON t.parent_id = pt.id
"""


def _row_to_catalog_row(row: sqlite3.Row) -> CatalogRow:
    condition_code = row["condition"]
    return CatalogRow(
        set_num=str(row["set_num"]),
        parent_theme=str(row["parent_theme"] or ""),
        theme=str(row["theme"] or ""),
        name=str(row["name"] or ""),
        num_parts=row["num_parts"],
        year=row["year"],
        condition=None if condition_code is None else Condition.from_code(condition_code),
        note=str(row["note"] or ""),
    )


def _naturally_sorted(rows: list[CatalogRow]) -> list[CatalogRow]:
    return sorted(rows, key=lambda row: SetNumber(row.set_num).sort_key)


def _escape_like_pattern(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SQLiteCatalogRepository:
    """Read-only queries over the LEGO set catalog."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def _fetch(self, where_clause: str = "", params: tuple = ()) -> list[CatalogRow]:
        query = f"SELECT {_ROW_COLUMNS_SQL} {_CATALOG_FROM_SQL} {where_clause}"
        with self._db.read_only() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_row_to_catalog_row(row) for row in rows]

    def search_by_prefix(self, prefix: str) -> list[CatalogRow]:
        pattern = f"{_escape_like_pattern(prefix)}%"
        rows = self._fetch("WHERE s.set_num LIKE ? ESCAPE '\\'", (pattern,))
        return _naturally_sorted(rows)

    def get(self, set_number: SetNumber) -> Optional[CatalogRow]:
        rows = self._fetch("WHERE s.set_num = ?", (str(set_number),))
        return rows[0] if rows else None

    def related(self, set_number: SetNumber) -> list[CatalogRow]:
        with self._db.read_only() as conn:
            source = conn.execute(
                "SELECT theme_id, year FROM sets WHERE set_num = ?",
                (str(set_number),),
            ).fetchone()
        if source is None or source["theme_id"] is None or source["year"] is None:
            return []

        rows = self._fetch(
            "WHERE s.theme_id = ? AND s.year = ? AND s.set_num != ?",
            (source["theme_id"], source["year"], str(set_number)),
        )
        # Richest set first, natural set-number order as the tiebreaker.
        return sorted(rows, key=lambda row: (-(row.num_parts or 0), SetNumber(row.set_num).sort_key))

    def exists(self, set_number: SetNumber) -> bool:
        with self._db.read_only() as conn:
            row = conn.execute("SELECT 1 FROM sets WHERE set_num = ?", (str(set_number),)).fetchone()
        return row is not None


class SQLiteOwnedRepository:
    """
    Read/write access to the owned-set inventory.

    Every mutating method opens (and commits) its own transaction unless
    called from inside a ``with owned_repo.transaction():`` block, in which
    case it joins that already-open transaction instead. This is what lets
    the command-language executor and the backup importer apply several
    mutations as a single all-or-nothing unit without every method needing
    an explicit connection argument.

    ``clock`` defaults to :func:`datetime.date.today` and is only ever
    overridden in tests, so a set's recorded add-date can be checked
    deterministically instead of against whatever "today" happens to be.
    """

    def __init__(self, db: Database, *, clock: Callable[[], date] = date.today) -> None:
        self._db = db
        self._active_conn: Optional[sqlite3.Connection] = None
        self._clock = clock

    def _run(self, operation: Callable[[sqlite3.Connection], _T]) -> _T:
        if self._active_conn is not None:
            return operation(self._active_conn)
        with self._db.transaction() as conn:
            return operation(conn)

    def _run_read(self, operation: Callable[[sqlite3.Connection], _T]) -> _T:
        if self._active_conn is not None:
            return operation(self._active_conn)
        with self._db.read_only() as conn:
            return operation(conn)

    @contextmanager
    def transaction(self) -> Iterator["SQLiteOwnedRepository"]:
        if self._active_conn is not None:
            # Already inside a transaction (nested use) -- just reuse it.
            yield self
            return
        with self._db.transaction() as conn:
            self._active_conn = conn
            try:
                yield self
            finally:
                self._active_conn = None

    def list(self, condition: Optional[Condition] = None) -> list[CatalogRow]:
        def operation(conn: sqlite3.Connection) -> list[CatalogRow]:
            query = f"SELECT {_ROW_COLUMNS_SQL} {_OWNED_FROM_SQL}"
            params: tuple = ()
            if condition is not None:
                query += " WHERE o.condition = ?"
                params = (int(condition),)
            rows = conn.execute(query, params).fetchall()
            return _naturally_sorted([_row_to_catalog_row(row) for row in rows])

        return self._run_read(operation)

    def is_owned(self, set_number: SetNumber) -> bool:
        def operation(conn: sqlite3.Connection) -> bool:
            row = conn.execute(
                "SELECT 1 FROM owned_sets WHERE set_num = ?", (str(set_number),)
            ).fetchone()
            return row is not None

        return self._run_read(operation)

    def set_exists_in_catalog(self, set_number: SetNumber) -> bool:
        def operation(conn: sqlite3.Connection) -> bool:
            row = conn.execute("SELECT 1 FROM sets WHERE set_num = ?", (str(set_number),)).fetchone()
            return row is not None

        return self._run_read(operation)

    def add(self, set_number: SetNumber) -> bool:
        def operation(conn: sqlite3.Connection) -> bool:
            if conn.execute("SELECT 1 FROM sets WHERE set_num = ?", (str(set_number),)).fetchone() is None:
                return False
            if conn.execute(
                "SELECT 1 FROM owned_sets WHERE set_num = ?", (str(set_number),)
            ).fetchone() is not None:
                return False
            conn.execute(
                "INSERT INTO owned_sets (set_num, condition, note, added_at) VALUES (?, 0, NULL, ?)",
                (str(set_number), self._clock().isoformat()),
            )
            return True

        return self._run(operation)

    def remove(self, set_number: SetNumber) -> bool:
        def operation(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute("DELETE FROM owned_sets WHERE set_num = ?", (str(set_number),))
            return cursor.rowcount > 0

        return self._run(operation)

    def set_condition(self, set_number: SetNumber, condition: Condition) -> bool:
        def operation(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "UPDATE owned_sets SET condition = ? WHERE set_num = ?",
                (int(condition), str(set_number)),
            )
            return cursor.rowcount > 0

        return self._run(operation)

    def set_note(self, set_number: SetNumber, note: str) -> bool:
        def operation(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "UPDATE owned_sets SET note = ? WHERE set_num = ?",
                (note, str(set_number)),
            )
            return cursor.rowcount > 0

        return self._run(operation)

    def clear_all(self) -> None:
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM owned_sets")

        self._run(operation)

    def toggle(self, set_number: SetNumber) -> bool:
        def operation(conn: sqlite3.Connection) -> bool:
            exists = conn.execute(
                "SELECT 1 FROM owned_sets WHERE set_num = ?", (str(set_number),)
            ).fetchone()
            if exists is not None:
                conn.execute("DELETE FROM owned_sets WHERE set_num = ?", (str(set_number),))
                return False
            conn.execute(
                "INSERT INTO owned_sets (set_num, condition, note, added_at) VALUES (?, 0, NULL, ?)",
                (str(set_number), self._clock().isoformat()),
            )
            return True

        return self._run(operation)

    def last_added_date(self) -> Optional[date]:
        def operation(conn: sqlite3.Connection) -> Optional[date]:
            row = conn.execute("SELECT MAX(added_at) FROM owned_sets").fetchone()
            value = row[0] if row else None
            return date.fromisoformat(value) if value else None

        return self._run_read(operation)
