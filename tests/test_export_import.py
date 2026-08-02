from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import conftest  # noqa: F401  (adds src/ to sys.path)

from lego_db.application.command_language.parser import parse
from lego_db.domain.value_objects import Condition, SetNumber
from lego_db.infrastructure.database import Database
from lego_db.infrastructure.exporters import export_filename_stem, export_owned_sets
from lego_db.infrastructure.importers import find_latest_backup_file, import_owned_sets
from lego_db.infrastructure.repositories import SQLiteOwnedRepository
from lego_db.infrastructure.schema import initialize_schema


class _FakeClock:
    """A settable stand-in for datetime.date.today, so 'added' dates in
    these tests are deterministic instead of tied to whatever day the
    test happens to run on."""

    def __init__(self, today: date) -> None:
        self.today = today

    def __call__(self) -> date:
        return self.today


def _seed_catalog(db: Database) -> None:
    with db.transaction() as conn:
        conn.execute("INSERT INTO themes (id, name, parent_id) VALUES (1, 'Technic', NULL)")
        conn.executemany(
            "INSERT INTO sets (set_num, name, year, theme_id, num_parts) VALUES (?, ?, ?, ?, ?)",
            [
                ("1234-1", "Galaxy Explorer", 1989, 1, 321),
                ("5678-1", "Space Cruiser", 1990, 1, 200),
                ("9999-1", "Untouched Set", 1991, 1, 50),
            ],
        )


class _TempDatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.db = Database(self.tmp_path / "lego.db")
        self.export_dir = self.tmp_path / "exports"
        initialize_schema(self.db)
        _seed_catalog(self.db)
        self.clock = _FakeClock(date(2026, 1, 1))
        self.owned = SQLiteOwnedRepository(self.db, clock=self.clock)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class ExportFilenameTests(_TempDatabaseTestCase):
    def test_uses_todays_date_when_nothing_is_owned(self) -> None:
        expected = f"owned_{date.today():%y%m%d}"
        stem = export_filename_stem(self.owned)
        self.assertEqual(stem, expected)

    def test_uses_the_most_recent_added_date_not_the_export_date(self) -> None:
        self.clock.today = date(2026, 1, 1)
        self.owned.add(SetNumber("1234-1"))

        self.clock.today = date(2026, 3, 20)
        self.owned.add(SetNumber("5678-1"))

        # Exporting "today" (a third, later date) must still use the most
        # recent *added* date (2026-03-20), not today's date.
        stem = export_filename_stem(self.owned)
        self.assertEqual(stem, "owned_260320")

    def test_export_writes_files_named_after_the_last_added_date(self) -> None:
        self.clock.today = date(2025, 12, 25)
        self.owned.add(SetNumber("1234-1"))

        txt_path, csv_path = export_owned_sets(self.owned, self.export_dir)
        self.assertEqual(txt_path.name, "owned_251225.txt")
        self.assertEqual(csv_path.name, "owned_251225.csv")
        self.assertTrue(txt_path.is_file())
        self.assertTrue(csv_path.is_file())


class ExportContentUnchangedTests(_TempDatabaseTestCase):
    """The filename changed; the content format did not."""

    def test_txt_content_is_still_replayable_command_tokens(self) -> None:
        self.owned.add(SetNumber("1234-1"))
        self.owned.set_condition(SetNumber("1234-1"), Condition.GOOD)
        self.owned.set_note(SetNumber("1234-1"), "great box")
        self.owned.add(SetNumber("9999-1"))

        txt_path, _ = export_owned_sets(self.owned, self.export_dir)
        text = txt_path.read_text(encoding="utf-8")

        self.assertIn("+1234-1", text)
        self.assertIn("2[great box]>1234-1", text)
        self.assertIn("+9999-1", text)

        plan = parse(text)
        self.assertFalse(plan.malformed)
        self.assertEqual(set(plan.add), {"1234-1", "9999-1"})

    def test_csv_content_is_unchanged_in_shape(self) -> None:
        self.owned.add(SetNumber("1234-1"))
        _, csv_path = export_owned_sets(self.owned, self.export_dir)
        lines = csv_path.read_text(encoding="utf-8-sig").splitlines()
        self.assertIn("1234-1", lines[1])
        # No added-date column leaked into the export -- content format
        # is exactly what it was before.
        self.assertEqual(len(lines[0].split(",")), 8)


class FindLatestBackupFileTests(_TempDatabaseTestCase):
    def test_returns_none_when_directory_does_not_exist(self) -> None:
        self.assertIsNone(find_latest_backup_file(self.tmp_path / "does_not_exist"))

    def test_returns_none_when_no_matching_files_present(self) -> None:
        self.export_dir.mkdir(parents=True)
        (self.export_dir / "notes.txt").write_text("irrelevant", encoding="utf-8")
        self.assertIsNone(find_latest_backup_file(self.export_dir))

    def test_ignores_files_not_matching_the_pattern_exactly(self) -> None:
        self.export_dir.mkdir(parents=True)
        # None of these should be mistaken for a dated backup file.
        for name in ("owned_export.txt", "owned_2026-01-01.txt", "owned_26011.txt", "owned_2601011.txt"):
            (self.export_dir / name).write_text("+1234-1", encoding="utf-8")
        self.assertIsNone(find_latest_backup_file(self.export_dir))

    def test_picks_the_most_recent_of_several_dated_backups(self) -> None:
        self.export_dir.mkdir(parents=True)
        for name in ("owned_250101.txt", "owned_260320.txt", "owned_260101.txt"):
            (self.export_dir / name).write_text("+1234-1", encoding="utf-8")
        found = find_latest_backup_file(self.export_dir)
        self.assertEqual(found.name, "owned_260320.txt")


class RoundTripTests(_TempDatabaseTestCase):
    def test_export_then_import_restores_identical_inventory(self) -> None:
        self.clock.today = date(2026, 2, 14)
        self.owned.add(SetNumber("1234-1"))
        self.owned.set_condition(SetNumber("1234-1"), Condition.GOOD)
        self.owned.set_note(SetNumber("1234-1"), "great box")
        self.owned.add(SetNumber("9999-1"))

        export_owned_sets(self.owned, self.export_dir)
        self.owned.clear_all()
        self.assertEqual(self.owned.list(), [])

        result = import_owned_sets(self.owned, self.export_dir)
        self.assertTrue(result.changed)
        self.assertFalse(result.malformed)

        restored = {row.set_num: row for row in self.owned.list()}
        self.assertEqual(set(restored), {"1234-1", "9999-1"})
        self.assertEqual(restored["1234-1"].condition, Condition.GOOD)
        self.assertEqual(restored["1234-1"].note, "great box")

    def test_import_uses_the_latest_backup_when_several_exist(self) -> None:
        self.export_dir.mkdir(parents=True)
        (self.export_dir / "owned_250101.txt").write_text("+9999-1", encoding="utf-8")
        (self.export_dir / "owned_260320.txt").write_text("+1234-1", encoding="utf-8")

        import_owned_sets(self.owned, self.export_dir)

        owned_now = {row.set_num for row in self.owned.list()}
        self.assertEqual(owned_now, {"1234-1"})

    def test_old_style_fixed_filename_is_not_recognized(self) -> None:
        self.export_dir.mkdir(parents=True)
        (self.export_dir / "owned_export.txt").write_text("+1234-1", encoding="utf-8")

        with self.assertRaises(FileNotFoundError):
            import_owned_sets(self.owned, self.export_dir)

    def test_import_raises_when_no_backup_file_is_present(self) -> None:
        with self.assertRaises(FileNotFoundError):
            import_owned_sets(self.owned, self.export_dir)

    def test_import_of_malformed_backup_changes_nothing(self) -> None:
        self.owned.add(SetNumber("1234-1"))
        export_owned_sets(self.owned, self.export_dir)

        # Overwrite the (correctly named) backup with garbage content.
        backup = find_latest_backup_file(self.export_dir)
        backup.write_text("not a valid command line", encoding="utf-8")

        result = import_owned_sets(self.owned, self.export_dir)
        self.assertTrue(result.malformed)
        self.assertEqual({row.set_num for row in self.owned.list()}, {"1234-1"})

    def test_restore_is_atomic_original_inventory_survives_a_failure(self) -> None:
        self.owned.add(SetNumber("1234-1"))
        self.owned.set_condition(SetNumber("1234-1"), Condition.GOOD)
        self.owned.set_note(SetNumber("1234-1"), "great box")
        self.owned.add(SetNumber("9999-1"))
        export_owned_sets(self.owned, self.export_dir)
        original_owned = {row.set_num for row in self.owned.list()}

        with patch.object(SQLiteOwnedRepository, "add", side_effect=RuntimeError("simulated disk failure")):
            with self.assertRaises(RuntimeError):
                import_owned_sets(self.owned, self.export_dir)

        restored = {row.set_num: row for row in self.owned.list()}
        self.assertEqual(set(restored), original_owned)
        self.assertEqual(restored["1234-1"].condition, Condition.GOOD)
        self.assertEqual(restored["1234-1"].note, "great box")


if __name__ == "__main__":
    unittest.main()
