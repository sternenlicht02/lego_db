"""
SQLite connection handling.

Every operation opens its own short-lived connection rather than keeping
one open for the life of the app -- simpler lifecycle (nothing to close on
exit, nothing shared across the language-selection bootstrap window and
the main window), and cheap enough for a local single-user file that the
overhead is not worth worrying about.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Iterator


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 3000")
        with suppress(sqlite3.DatabaseError):
            conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def read_only(self) -> Iterator[sqlite3.Connection]:
        """A connection for SELECT-only use. Always closed on exit."""
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """One atomic read/write transaction: commits on success, rolls back on any exception."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            with suppress(Exception):
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def script(self, sql: str) -> None:
        """
        Run a multi-statement DDL script (e.g. schema creation).

        ``executescript`` issues its own implicit COMMIT before running, so
        it is deliberately not combined with the explicit BEGIN/COMMIT in
        ``transaction()`` above -- doing so raises "cannot commit - no
        transaction is active" once ``executescript`` has already closed
        out the transaction on its own.
        """
        conn = self._connect()
        try:
            conn.executescript(sql)
        finally:
            conn.close()
