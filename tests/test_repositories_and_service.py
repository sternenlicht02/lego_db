from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import conftest  # noqa: F401  (adds src/ to sys.path)

from lego_db.application.service import CatalogService
from lego_db.domain.value_objects import Condition, SetNumber
from lego_db.infrastructure.database import Database
from lego_db.infrastructure.repositories import SQLiteCatalogRepository, SQLiteOwnedRepository
from lego_db.infrastructure.schema import initialize_schema


class _FakeClock:
    """A settable stand-in for datetime.date.today, for deterministic dates in tests."""

    def __init__(self, today: date) -> None:
        self.today = today

    def __call__(self) -> date:
        return self.today


def _seed(db: Database) -> None:
    with db.transaction() as conn:
        conn.executemany(
            "INSERT INTO themes (id, name, parent_id) VALUES (?, ?, ?)",
            [
                (1, "Technic", None),
                (67, "Town", None),
                (761, "Ninjago", 67),
            ],
        )
        conn.executemany(
            "INSERT INTO sets (set_num, name, year, theme_id, num_parts) VALUES (?, ?, ?, ?, ?)",
            [
                ("1234-1", "Galaxy Explorer", 1989, 1, 321),
                ("1234-2", "Galaxy Explorer Reissue", 1989, 1, 321),
                ("20-1", "Small Car", 1970, 67, 10),
                ("100-1", "Big Truck", 1970, 67, 400),
                ("100STORES-1", "100 LEGO Stores", 2019, 761, 5),
                ("201908-mmb", "Owl", 2019, 761, 32),
                ("7777-1", "Deep Sea", 1970, 67, 120),
            ],
        )
        conn.execute(
            "INSERT INTO owned_sets (set_num, condition, note, added_at) VALUES (?, ?, ?, ?)",
            ("1234-1", 2, "display only", "2026-01-01"),
        )


class _TempDatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self._tmp.name) / "lego.db")
        initialize_schema(self.db)
        _seed(self.db)
        self.catalog = SQLiteCatalogRepository(self.db)
        self.owned = SQLiteOwnedRepository(self.db)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class CatalogRepositoryTests(_TempDatabaseTestCase):
    def test_search_by_prefix_matches_and_joins_theme(self) -> None:
        rows = self.catalog.search_by_prefix("1234")
        self.assertEqual({row.set_num for row in rows}, {"1234-1", "1234-2"})
        row = next(r for r in rows if r.set_num == "1234-1")
        self.assertEqual(row.theme, "Technic")
        self.assertEqual(row.condition, Condition.GOOD)
        self.assertEqual(row.note, "display only")

    def test_search_by_prefix_is_naturally_sorted(self) -> None:
        rows = self.catalog.search_by_prefix("")
        numbers = [row.set_num for row in rows]
        self.assertLess(numbers.index("20-1"), numbers.index("100-1"))
        self.assertLess(numbers.index("100-1"), numbers.index("100STORES-1"))

    def test_get_returns_joined_row_or_none(self) -> None:
        row = self.catalog.get(SetNumber("100STORES-1"))
        self.assertIsNotNone(row)
        self.assertEqual(row.parent_theme, "Town")
        self.assertIsNone(self.catalog.get(SetNumber("9999-1")))

    def test_related_matches_same_theme_and_year_excludes_self_sorted_by_size(self) -> None:
        related = self.catalog.related(SetNumber("20-1"))
        # Same theme_id (67) and year (1970) as "20-1"; sorted richest-first.
        self.assertEqual([row.set_num for row in related], ["100-1", "7777-1"])

    def test_related_is_empty_when_theme_or_year_missing(self) -> None:
        self.assertEqual(self.catalog.related(SetNumber("9999-1")), [])

    def test_exists(self) -> None:
        self.assertTrue(self.catalog.exists(SetNumber("20-1")))
        self.assertFalse(self.catalog.exists(SetNumber("9999-1")))


class OwnedRepositoryTests(_TempDatabaseTestCase):
    def test_add_requires_catalog_membership(self) -> None:
        self.assertFalse(self.owned.add(SetNumber("9999-1")))
        self.assertTrue(self.owned.add(SetNumber("20-1")))
        self.assertTrue(self.owned.is_owned(SetNumber("20-1")))

    def test_add_twice_is_a_no_op(self) -> None:
        self.assertTrue(self.owned.add(SetNumber("20-1")))
        self.assertFalse(self.owned.add(SetNumber("20-1")))

    def test_remove_reports_whether_anything_changed(self) -> None:
        self.assertFalse(self.owned.remove(SetNumber("20-1")))
        self.owned.add(SetNumber("20-1"))
        self.assertTrue(self.owned.remove(SetNumber("20-1")))

    def test_set_condition_and_note_require_existing_owned_row(self) -> None:
        self.assertFalse(self.owned.set_condition(SetNumber("20-1"), Condition.BAD))
        self.owned.add(SetNumber("20-1"))
        self.assertTrue(self.owned.set_condition(SetNumber("20-1"), Condition.BAD))
        self.assertTrue(self.owned.set_note(SetNumber("20-1"), "hello"))
        row = self.owned.list()[0]
        self.assertEqual(row.condition, Condition.BAD)
        self.assertEqual(row.note, "hello")

    def test_toggle_adds_then_removes(self) -> None:
        self.assertTrue(self.owned.toggle(SetNumber("20-1")))
        self.assertTrue(self.owned.is_owned(SetNumber("20-1")))
        self.assertFalse(self.owned.toggle(SetNumber("20-1")))
        self.assertFalse(self.owned.is_owned(SetNumber("20-1")))

    def test_list_filters_by_condition(self) -> None:
        self.owned.add(SetNumber("20-1"))
        self.owned.set_condition(SetNumber("20-1"), Condition.BAD)
        self.assertEqual(len(self.owned.list(Condition.GOOD)), 1)  # the seeded 1234-1
        self.assertEqual(len(self.owned.list(Condition.BAD)), 1)  # 20-1
        self.assertEqual(len(self.owned.list(None)), 2)

    def test_last_added_date_is_none_when_nothing_owned(self) -> None:
        # The shared setUp() seeds one owned row, so use a separate,
        # genuinely empty database to test the true "nothing owned" case.
        with tempfile.TemporaryDirectory() as empty_tmp:
            empty_db = Database(Path(empty_tmp) / "empty.db")
            initialize_schema(empty_db)
            self.assertIsNone(SQLiteOwnedRepository(empty_db).last_added_date())

    def test_last_added_date_reflects_the_most_recent_add(self) -> None:
        with tempfile.TemporaryDirectory() as isolated_tmp:
            db = Database(Path(isolated_tmp) / "isolated.db")
            initialize_schema(db)
            with db.transaction() as conn:
                conn.execute("INSERT INTO sets (set_num, name) VALUES ('20-1', 'Small Car')")
                conn.execute("INSERT INTO sets (set_num, name) VALUES ('100-1', 'Big Truck')")

            clock = _FakeClock(date(2026, 1, 1))
            owned = SQLiteOwnedRepository(db, clock=clock)

            owned.add(SetNumber("20-1"))
            self.assertEqual(owned.last_added_date(), date(2026, 1, 1))

            clock.today = date(2026, 5, 17)
            owned.add(SetNumber("100-1"))
            self.assertEqual(owned.last_added_date(), date(2026, 5, 17))

            # Re-adding an already-owned set is a no-op and must not
            # update the most-recent-add date.
            clock.today = date(2026, 12, 31)
            owned.add(SetNumber("100-1"))
            self.assertEqual(owned.last_added_date(), date(2026, 5, 17))

    def test_toggle_records_added_date_on_the_add_branch(self) -> None:
        clock_date = date(2026, 7, 4)
        owned = SQLiteOwnedRepository(self.db, clock=lambda: clock_date)
        owned.toggle(SetNumber("20-1"))
        self.assertEqual(owned.last_added_date(), date(2026, 7, 4))

    def test_transaction_rolls_back_all_operations_on_failure(self) -> None:
        with self.assertRaises(RuntimeError):
            with self.owned.transaction() as repo:
                repo.add(SetNumber("20-1"))
                repo.add(SetNumber("100-1"))
                raise RuntimeError("simulated failure mid-transaction")
        # Neither add should have survived: the whole unit rolled back.
        self.assertFalse(self.owned.is_owned(SetNumber("20-1")))
        self.assertFalse(self.owned.is_owned(SetNumber("100-1")))

    def test_transaction_commits_all_operations_together(self) -> None:
        with self.owned.transaction() as repo:
            repo.add(SetNumber("20-1"))
            repo.add(SetNumber("100-1"))
        self.assertTrue(self.owned.is_owned(SetNumber("20-1")))
        self.assertTrue(self.owned.is_owned(SetNumber("100-1")))


class CatalogServiceSearchTests(_TempDatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.service = CatalogService(self.catalog, self.owned)

    def test_empty_query_lists_everything(self) -> None:
        self.assertEqual(len(self.service.search("")), 7)

    def test_plain_prefix_search(self) -> None:
        rows = self.service.search("1234")
        self.assertEqual({r.set_num for r in rows}, {"1234-1", "1234-2"})

    def test_owned_keyword_english_and_korean(self) -> None:
        self.owned.add(SetNumber("20-1"))
        for keyword in ("owned", "OWNED", "보유"):
            with self.subTest(keyword=keyword):
                rows = self.service.search(keyword)
                self.assertEqual({r.set_num for r in rows}, {"1234-1", "20-1"})

    def test_owned_keyword_with_condition_filter(self) -> None:
        self.owned.add(SetNumber("20-1"))
        self.owned.set_condition(SetNumber("20-1"), Condition.BAD)
        rows = self.service.search("owned 1")
        self.assertEqual([r.set_num for r in rows], ["20-1"])

    def test_owned_keyword_with_invalid_condition_returns_empty(self) -> None:
        self.assertEqual(self.service.search("owned 9"), [])
        self.assertEqual(self.service.search("owned abc"), [])


class CatalogServiceModificationTests(_TempDatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.service = CatalogService(self.catalog, self.owned)

    def test_add_remove_condition_note_round_trip(self) -> None:
        result = self.service.apply_modification("+20-1 2>20-1 [a note]>20-1")
        self.assertTrue(result.changed)
        self.assertFalse(result.partial)
        self.assertFalse(result.malformed)

        row = self.service.get_detail("20-1")
        self.assertEqual(row.condition, Condition.GOOD)
        self.assertEqual(row.note, "a note")

    def test_re_adding_owned_set_is_not_marked_partial(self) -> None:
        self.service.apply_modification("+20-1")
        result = self.service.apply_modification("+20-1")
        self.assertFalse(result.changed)
        self.assertFalse(result.partial)
        self.assertFalse(result.malformed)

    def test_condition_on_non_owned_set_is_partial(self) -> None:
        result = self.service.apply_modification("2>20-1")
        self.assertFalse(result.changed)
        self.assertTrue(result.partial)

    def test_malformed_input_changes_nothing(self) -> None:
        result = self.service.apply_modification("garbage +20-1")
        self.assertTrue(result.malformed)
        self.assertFalse(self.service.is_owned("20-1"))

    def test_modification_targets_alphanumeric_set_numbers(self) -> None:
        result = self.service.apply_modification("+100STORES-1 1[nice]>100STORES-1")
        self.assertTrue(result.changed)
        self.assertFalse(result.partial)
        row = self.service.get_detail("100STORES-1")
        self.assertEqual(row.condition, Condition.BAD)
        self.assertEqual(row.note, "nice")

    def test_add_of_unknown_set_number_is_partial(self) -> None:
        result = self.service.apply_modification("+9999-1")
        self.assertFalse(result.changed)
        self.assertTrue(result.partial)


if __name__ == "__main__":
    unittest.main()
