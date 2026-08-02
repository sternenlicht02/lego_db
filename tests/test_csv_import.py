from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import conftest  # noqa: F401  (adds src/ to sys.path)

from lego_db.infrastructure.csv_import import CsvCatalogImporter
from lego_db.infrastructure.database import Database


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


class _ImporterTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.db = Database(self.tmp_path / "lego.db")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _importer(self, themes_rows, sets_rows, on_progress=None) -> CsvCatalogImporter:
        themes_csv = self.tmp_path / "themes.csv"
        sets_csv = self.tmp_path / "sets.csv"
        _write_csv(themes_csv, ["id", "name", "parent_id"], themes_rows)
        _write_csv(sets_csv, ["set_num", "name", "year", "theme_id", "num_parts", "img_url"], sets_rows)
        return CsvCatalogImporter(self.db, sets_csv=sets_csv, themes_csv=themes_csv, on_progress=on_progress)


class CsvCatalogImporterTests(_ImporterTestBase):

    def test_imports_valid_rows(self) -> None:
        importer = self._importer(
            themes_rows=[[1, "Technic", ""], [18, "Star Wars", 1]],
            sets_rows=[["1234-1", "Galaxy Explorer", 1989, 1, 321, "http://x"]],
        )
        themes_summary, sets_summary = importer.run()

        self.assertEqual(themes_summary.imported_rows, 2)
        self.assertEqual(sets_summary.imported_rows, 1)

        with self.db.read_only() as conn:
            theme = conn.execute("SELECT * FROM themes WHERE id = 18").fetchone()
            lego_set = conn.execute("SELECT * FROM sets WHERE set_num = '1234-1'").fetchone()

        self.assertEqual(theme["parent_id"], 1)
        self.assertEqual(lego_set["name"], "Galaxy Explorer")
        self.assertEqual(lego_set["year"], 1989)

    def test_skips_rows_with_bad_integers_but_keeps_going(self) -> None:
        importer = self._importer(
            themes_rows=[[1, "Technic", ""]],
            sets_rows=[
                ["1234-1", "Good Set", 1989, 1, 321, ""],
                ["bad-1", "Bad Year", "not-a-year", 1, 10, ""],
            ],
        )
        _themes_summary, sets_summary = importer.run()
        self.assertEqual(sets_summary.imported_rows, 1)
        self.assertEqual(sets_summary.skipped_rows, 1)

        with self.db.read_only() as conn:
            row = conn.execute("SELECT * FROM sets WHERE set_num = 'bad-1'").fetchone()
        self.assertIsNone(row)

    def test_set_referencing_missing_theme_is_kept_with_null_theme(self) -> None:
        importer = self._importer(
            themes_rows=[[1, "Technic", ""]],
            sets_rows=[["1234-1", "Orphan", 1989, 999, 321, ""]],
        )
        importer.run()
        with self.db.read_only() as conn:
            row = conn.execute("SELECT theme_id FROM sets WHERE set_num = '1234-1'").fetchone()
        self.assertIsNone(row["theme_id"])

    def test_running_twice_updates_rather_than_duplicates(self) -> None:
        importer = self._importer(
            themes_rows=[[1, "Technic", ""]],
            sets_rows=[["1234-1", "Original Name", 1989, 1, 321, ""]],
        )
        importer.run()

        importer2 = self._importer(
            themes_rows=[[1, "Technic", ""]],
            sets_rows=[["1234-1", "Renamed", 1990, 1, 400, ""]],
        )
        importer2.run()

        with self.db.read_only() as conn:
            rows = conn.execute("SELECT * FROM sets").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Renamed")
        self.assertEqual(rows[0]["year"], 1990)

    def test_raises_when_csv_files_are_missing(self) -> None:
        importer = CsvCatalogImporter(
            self.db, sets_csv=self.tmp_path / "missing_sets.csv", themes_csv=self.tmp_path / "missing_themes.csv"
        )
        with self.assertRaises(FileNotFoundError):
            importer.run()


class ProgressCallbackTests(_ImporterTestBase):
    """
    The importer no longer renders progress itself -- it only reports
    (label, current, total), and a caller-supplied callback decides what
    to do with that. These tests check the callback contract directly,
    independent of the console/GUI reporters that consume it.
    """

    def test_on_progress_is_called_once_per_row_per_phase_plus_a_final_call(self) -> None:
        calls: list[tuple[str, int, int]] = []
        importer = self._importer(
            themes_rows=[[1, "Technic", ""], [18, "Star Wars", 1]],
            sets_rows=[["1234-1", "Galaxy Explorer", 1989, 1, 321, ""]],
            on_progress=lambda label, current, total: calls.append((label, current, total)),
        )
        importer.run()

        themes_calls = [c for c in calls if c[0] == "themes.csv"]
        sets_calls = [c for c in calls if c[0] == "sets.csv"]

        # 2 theme rows -> at least one call per row, and the final call
        # must report current == total.
        self.assertGreaterEqual(len(themes_calls), 2)
        self.assertEqual(themes_calls[-1], ("themes.csv", 2, 2))

        self.assertGreaterEqual(len(sets_calls), 1)
        self.assertEqual(sets_calls[-1], ("sets.csv", 1, 1))

    def test_on_progress_reports_total_zero_for_an_empty_csv(self) -> None:
        calls: list[tuple[str, int, int]] = []
        importer = self._importer(
            themes_rows=[],
            sets_rows=[],
            on_progress=lambda label, current, total: calls.append((label, current, total)),
        )
        importer.run()

        # Even with zero data rows, each phase must still report a
        # completion call so a progress window isn't left stuck at 0%.
        self.assertIn(("themes.csv", 0, 0), calls)
        self.assertIn(("sets.csv", 0, 0), calls)

    def test_defaults_to_console_reporter_without_raising_when_no_callback_given(self) -> None:
        # No on_progress passed -- must fall back to the console reporter
        # (which is a no-op here, since stdout isn't a real terminal
        # under the test runner) without erroring.
        importer = self._importer(
            themes_rows=[[1, "Technic", ""]],
            sets_rows=[["1234-1", "Galaxy Explorer", 1989, 1, 321, ""]],
        )
        importer.run()  # must not raise


if __name__ == "__main__":
    unittest.main()
