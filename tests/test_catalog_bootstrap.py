from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import conftest  # noqa: F401  (adds src/ to sys.path)

from lego_db.application.service import CatalogService
from lego_db.infrastructure.csv_import import CatalogDataMissingError, catalog_is_empty, ensure_catalog_populated
from lego_db.infrastructure.database import Database
from lego_db.infrastructure.repositories import SQLiteCatalogRepository, SQLiteOwnedRepository
from lego_db.infrastructure.schema import initialize_schema

_REAL_CSV_DIR = Path(__file__).resolve().parents[1] / "src" / "lego_db" / "data" / "csv"


class EnsureCatalogPopulatedTests(unittest.TestCase):
    """
    Regression tests for the bug reported against the shipped app: a fresh
    database (schema created, never imported) made every search return
    zero rows no matter what was typed, because nothing ever loaded the
    CSV data into it. ``build_presenter()`` now calls
    ``ensure_catalog_populated`` for exactly this reason.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self._tmp.name) / "lego.db")
        initialize_schema(self.db)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_fresh_schema_only_database_is_considered_empty(self) -> None:
        self.assertTrue(catalog_is_empty(self.db))

    def test_populates_from_the_real_bundled_csv_and_search_then_works(self) -> None:
        ran = ensure_catalog_populated(
            self.db, sets_csv=_REAL_CSV_DIR / "sets.csv", themes_csv=_REAL_CSV_DIR / "themes.csv"
        )
        self.assertTrue(ran)
        self.assertFalse(catalog_is_empty(self.db))

        service = CatalogService(SQLiteCatalogRepository(self.db), SQLiteOwnedRepository(self.db))
        rows = service.search("1")
        self.assertGreater(len(rows), 0, "search('1') must not return zero rows once the catalog is populated")

    def test_is_idempotent_does_not_reimport_once_populated(self) -> None:
        ensure_catalog_populated(self.db, sets_csv=_REAL_CSV_DIR / "sets.csv", themes_csv=_REAL_CSV_DIR / "themes.csv")
        with self.db.read_only() as conn:
            count_after_first = conn.execute("SELECT COUNT(*) FROM sets").fetchone()[0]

        ran_again = ensure_catalog_populated(
            self.db, sets_csv=_REAL_CSV_DIR / "sets.csv", themes_csv=_REAL_CSV_DIR / "themes.csv"
        )
        self.assertFalse(ran_again)

        with self.db.read_only() as conn:
            count_after_second = conn.execute("SELECT COUNT(*) FROM sets").fetchone()[0]
        self.assertEqual(count_after_first, count_after_second)

    def test_raises_clear_error_when_catalog_empty_and_csv_missing(self) -> None:
        missing_dir = Path(self._tmp.name) / "does_not_exist"
        with self.assertRaises(CatalogDataMissingError):
            ensure_catalog_populated(self.db, sets_csv=missing_dir / "sets.csv", themes_csv=missing_dir / "themes.csv")
        # And the database is still untouched/empty, not left half-initialized.
        self.assertTrue(catalog_is_empty(self.db))


if __name__ == "__main__":
    unittest.main()
