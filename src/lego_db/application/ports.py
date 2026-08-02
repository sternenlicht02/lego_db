"""
Repository ports.

The application layer depends only on these protocols, never on SQLite
directly, so the command language and presenters can be tested against a
plain in-memory fake instead of a real database file.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date
from typing import Optional, Protocol, Sequence

from lego_db.application.catalog_row import CatalogRow
from lego_db.domain.value_objects import Condition, SetNumber


class CatalogRepository(Protocol):
    """Read-only access to the LEGO set catalog (``sets`` + ``themes``)."""

    def search_by_prefix(self, prefix: str) -> Sequence[CatalogRow]:
        """Sets whose set number starts with ``prefix``, naturally sorted."""
        ...

    def get(self, set_number: SetNumber) -> Optional[CatalogRow]:
        ...

    def related(self, set_number: SetNumber) -> Sequence[CatalogRow]:
        """Other sets sharing the same theme and year, richest first."""
        ...

    def exists(self, set_number: SetNumber) -> bool:
        ...


class OwnedRepository(Protocol):
    """Read/write access to the user's owned-set inventory."""

    def list(self, condition: Optional[Condition] = None) -> Sequence[CatalogRow]:
        ...

    def is_owned(self, set_number: SetNumber) -> bool:
        ...

    def set_exists_in_catalog(self, set_number: SetNumber) -> bool:
        ...

    def add(self, set_number: SetNumber) -> bool:
        """Add ``set_number`` as owned. False if already owned or unknown."""
        ...

    def remove(self, set_number: SetNumber) -> bool:
        """Remove ``set_number`` from owned. False if it wasn't owned."""
        ...

    def set_condition(self, set_number: SetNumber, condition: Condition) -> bool:
        """False if ``set_number`` isn't currently owned."""
        ...

    def set_note(self, set_number: SetNumber, note: str) -> bool:
        """False if ``set_number`` isn't currently owned."""
        ...

    def toggle(self, set_number: SetNumber) -> bool:
        """Add if not owned, remove if owned. Returns the new owned state."""
        ...

    def clear_all(self) -> None:
        """Remove every owned-set row. Used only by backup restore."""
        ...

    def last_added_date(self) -> Optional[date]:
        """
        The most recent date any set was added to owned, or None if
        nothing is owned. Drives the export filename; not shown in the UI.
        """
        ...

    def transaction(self) -> AbstractContextManager["OwnedRepository"]:
        """
        Run several of the methods above as one atomic unit.

        Used where multiple mutations must all succeed or all fail
        together (applying a multi-token command, restoring a backup).
        """
        ...
