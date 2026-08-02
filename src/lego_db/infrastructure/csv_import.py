"""
Imports the Rebrickable ``sets.csv`` / ``themes.csv`` dataset into the
local SQLite catalog.

Row-level problems (a bad integer, a theme that references a parent that
doesn't exist, a duplicate id) are logged and skipped rather than aborting
the whole import -- a ~27k-row public dataset reliably has a handful of
these, and failing the entire build over one bad row would be worse than
just reporting it.
"""

from __future__ import annotations

import csv
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from lego_db.infrastructure.database import Database
from lego_db.infrastructure.schema import initialize_schema

_LOGGER = logging.getLogger(__name__)

# (label, current, total) -- called once per row processed, with a final
# call at current == total marking that phase as done. The importer
# itself doesn't render anything; a reporter decides how (or whether) to
# show that. This is what lets the console script and the GUI's own
# setup window drive the exact same import with two different displays.
ProgressCallback = Callable[[str, int, int], None]


@dataclass(frozen=True, slots=True)
class ImportSummary:
    source: str
    total_rows: int
    imported_rows: int
    skipped_rows: int


@dataclass(frozen=True, slots=True)
class _ThemeRecord:
    theme_id: int
    name: str
    parent_id: Optional[int]


@dataclass(frozen=True, slots=True)
class _SetRecord:
    set_num: str
    name: str
    theme_id: Optional[int]
    num_parts: Optional[int]
    year: Optional[int]


class ProgressBar:
    """
    A minimal, dependency-free ASCII progress bar for a console.

    Renders carriage-return updates only when attached to a real
    terminal; when stdout is redirected (a log file, a pipe, a test
    runner) it stays silent, rather than writing one line per row
    processed. ``finish`` is idempotent, so calling it more than once
    (or after ``update`` already reached 100%) never re-renders the line.
    """

    def __init__(self, total: int, width: int = 30) -> None:
        self.total = max(int(total), 0)
        self.width = max(int(width), 1)
        self.start = time.perf_counter()
        self._interactive = sys.stdout.isatty()
        self._done = False

    def update(self, current: int, label: str = "") -> None:
        if not self._interactive or self._done:
            return
        current = max(int(current), 0)
        progress = min(max(current / self.total, 0.0), 1.0) if self.total > 0 else 1.0
        filled = int(self.width * progress)
        bar = "#" * filled + "-" * (self.width - filled)
        elapsed = time.perf_counter() - self.start
        eta = (elapsed / progress - elapsed) if progress > 0 else 0.0

        sys.stdout.write(f"\r[{bar}] {int(progress * 100):3d}% | ETA {eta:6.1f}s | {label}")
        sys.stdout.flush()

    def finish(self, label: str = "") -> None:
        if self._done:
            return
        if self._interactive:
            self.update(self.total, label=label)
            sys.stdout.write("\n")
            sys.stdout.flush()
        self._done = True


def console_progress_reporter() -> ProgressCallback:
    """
    The default :data:`ProgressCallback`: an ASCII :class:`ProgressBar`
    per phase (a new one whenever the label changes), matching what
    ``scripts/build_db.py`` has always shown on a console.
    """
    state: dict[str, object] = {"bar": None, "label": None}

    def report(label: str, current: int, total: int) -> None:
        if state["label"] != label:
            state["bar"] = ProgressBar(total)
            state["label"] = label
        bar: ProgressBar = state["bar"]  # type: ignore[assignment]
        if current >= total:
            bar.finish(label)
        else:
            bar.update(current, label)

    return report


def _clean_text(value: Optional[str]) -> str:
    return "" if value is None else str(value).strip()


def _parse_required_int(value: Optional[str], *, field_name: str, source: Path, row_no: int) -> int:
    text = _clean_text(value)
    if not text:
        raise ValueError(f"missing required field '{field_name}'")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(
            f"{source.name}: invalid integer in field '{field_name}' at row {row_no}: {text!r}"
        ) from exc


def _parse_optional_int(value: Optional[str], *, field_name: str, source: Path, row_no: int) -> Optional[int]:
    text = _clean_text(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(
            f"{source.name}: invalid integer in field '{field_name}' at row {row_no}: {text!r}"
        ) from exc


def _load_csv_rows(csv_path: Path, *, required_columns: set[str]) -> list[tuple[int, dict[str, str]]]:
    rows: list[tuple[int, dict[str, str]]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{csv_path.name}: missing header row")

        header = {str(name).strip() for name in reader.fieldnames if name is not None}
        missing = sorted(required_columns - header)
        if missing:
            raise ValueError(f"{csv_path.name}: missing required columns: {', '.join(missing)}")

        for row_no, row in enumerate(reader, start=2):
            normalized = {str(key).strip(): value for key, value in row.items() if key is not None}
            if normalized and any(_clean_text(value) for value in normalized.values()):
                rows.append((row_no, normalized))

    return rows


def _parse_theme_record(row: dict[str, str], *, source: Path, row_no: int) -> _ThemeRecord:
    theme_id = _parse_required_int(row.get("id"), field_name="id", source=source, row_no=row_no)
    name = _clean_text(row.get("name"))
    if not name:
        raise ValueError("missing required field 'name'")
    parent_id = _parse_optional_int(row.get("parent_id"), field_name="parent_id", source=source, row_no=row_no)
    return _ThemeRecord(theme_id=theme_id, name=name, parent_id=parent_id)


def _parse_set_record(row: dict[str, str], *, source: Path, row_no: int) -> _SetRecord:
    set_num = _clean_text(row.get("set_num"))
    if not set_num:
        raise ValueError("missing required field 'set_num'")
    name = _clean_text(row.get("name"))
    if not name:
        raise ValueError("missing required field 'name'")
    theme_id = _parse_optional_int(row.get("theme_id"), field_name="theme_id", source=source, row_no=row_no)
    num_parts = _parse_optional_int(row.get("num_parts"), field_name="num_parts", source=source, row_no=row_no)
    year = _parse_optional_int(row.get("year"), field_name="year", source=source, row_no=row_no)
    # img_url is present in the Rebrickable export but unused by this project.
    return _SetRecord(set_num=set_num, name=name, theme_id=theme_id, num_parts=num_parts, year=year)


class CsvCatalogImporter:
    def __init__(
        self,
        db: Database,
        *,
        sets_csv: Path,
        themes_csv: Path,
        on_progress: Optional[ProgressCallback] = None,
    ) -> None:
        self._db = db
        self._sets_csv = sets_csv
        self._themes_csv = themes_csv
        self._on_progress = on_progress or console_progress_reporter()

    def _load_theme_ids(self, conn) -> set[int]:
        return {int(row[0]) for row in conn.execute("SELECT id FROM themes").fetchall()}

    def _report(self, label: str, current: int, total: int) -> None:
        self._on_progress(label, current, total)

    def _import_themes(self, conn) -> ImportSummary:
        rows = _load_csv_rows(self._themes_csv, required_columns={"id", "name"})
        total = len(rows)
        label = self._themes_csv.name
        parsed: dict[int, _ThemeRecord] = {}
        skipped = 0

        for index, (row_no, row) in enumerate(rows, start=1):
            try:
                record = _parse_theme_record(row, source=self._themes_csv, row_no=row_no)
                if record.theme_id in parsed:
                    _LOGGER.warning(
                        "%s: duplicate theme id %s at row %d; last row wins",
                        self._themes_csv.name, record.theme_id, row_no,
                    )
                parsed[record.theme_id] = record
            except Exception as exc:
                skipped += 1
                _LOGGER.warning("[skip] %s:%d: %s", self._themes_csv.name, row_no, exc)
            self._report(label, index, total)
        self._report(label, total, total)  # covers the zero-row edge case too

        ordered = [parsed[theme_id] for theme_id in sorted(parsed)]
        conn.executemany(
            """
            INSERT INTO themes (id, name, parent_id) VALUES (?, ?, NULL)
            ON CONFLICT(id) DO UPDATE SET name = excluded.name, parent_id = NULL
            """,
            ((record.theme_id, record.name) for record in ordered),
        )

        known_theme_ids = self._load_theme_ids(conn)
        for record in ordered:
            parent_id = record.parent_id
            if parent_id is None:
                conn.execute("UPDATE themes SET parent_id = NULL WHERE id = ?", (record.theme_id,))
                continue
            if parent_id == record.theme_id:
                _LOGGER.warning(
                    "%s: theme %s references itself as parent_id; stored as NULL",
                    self._themes_csv.name, record.theme_id,
                )
                conn.execute("UPDATE themes SET parent_id = NULL WHERE id = ?", (record.theme_id,))
                continue
            if parent_id not in known_theme_ids:
                _LOGGER.warning(
                    "%s: theme %s references missing parent_id %s; stored as NULL",
                    self._themes_csv.name, record.theme_id, parent_id,
                )
                conn.execute("UPDATE themes SET parent_id = NULL WHERE id = ?", (record.theme_id,))
                continue
            conn.execute("UPDATE themes SET parent_id = ? WHERE id = ?", (parent_id, record.theme_id))

        return ImportSummary(
            source=self._themes_csv.name, total_rows=total, imported_rows=len(parsed), skipped_rows=skipped
        )

    def _import_sets(self, conn) -> ImportSummary:
        rows = _load_csv_rows(self._sets_csv, required_columns={"set_num", "name"})
        total = len(rows)
        label = self._sets_csv.name
        known_theme_ids = self._load_theme_ids(conn)
        parsed: dict[str, _SetRecord] = {}
        skipped = 0

        for index, (row_no, row) in enumerate(rows, start=1):
            try:
                record = _parse_set_record(row, source=self._sets_csv, row_no=row_no)
                if record.theme_id is not None and record.theme_id not in known_theme_ids:
                    _LOGGER.warning(
                        "%s: set %s references missing theme_id %s; stored as NULL",
                        self._sets_csv.name, record.set_num, record.theme_id,
                    )
                    record = _SetRecord(
                        set_num=record.set_num, name=record.name, theme_id=None,
                        num_parts=record.num_parts, year=record.year,
                    )
                if record.set_num in parsed:
                    _LOGGER.warning(
                        "%s: duplicate set_num %s at row %d; last row wins",
                        self._sets_csv.name, record.set_num, row_no,
                    )
                parsed[record.set_num] = record
            except Exception as exc:
                skipped += 1
                _LOGGER.warning("[skip] %s:%d: %s", self._sets_csv.name, row_no, exc)
            self._report(label, index, total)
        self._report(label, total, total)  # covers the zero-row edge case too

        ordered = [parsed[set_num] for set_num in sorted(parsed)]
        conn.executemany(
            """
            INSERT INTO sets (set_num, name, theme_id, num_parts, year) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(set_num) DO UPDATE SET
                name = excluded.name, theme_id = excluded.theme_id,
                num_parts = excluded.num_parts, year = excluded.year
            """,
            (
                (record.set_num, record.name, record.theme_id, record.num_parts, record.year)
                for record in ordered
            ),
        )

        return ImportSummary(
            source=self._sets_csv.name, total_rows=total, imported_rows=len(parsed), skipped_rows=skipped
        )

    def run(self) -> tuple[ImportSummary, ImportSummary]:
        missing = [p for p in (self._themes_csv, self._sets_csv) if not p.is_file()]
        if missing:
            names = ", ".join(str(p) for p in missing)
            raise FileNotFoundError(f"required CSV file(s) not found: {names}")

        initialize_schema(self._db)
        with self._db.transaction() as conn:
            themes_summary = self._import_themes(conn)
            sets_summary = self._import_sets(conn)
        return themes_summary, sets_summary


class CatalogDataMissingError(Exception):
    """Raised when the catalog is empty and its source CSV files are missing too."""

    def __init__(self, sets_csv: Path, themes_csv: Path) -> None:
        super().__init__(f"catalog CSV files not found: {sets_csv}, {themes_csv}")
        self.sets_csv = sets_csv
        self.themes_csv = themes_csv


def catalog_is_empty(db: Database) -> bool:
    with db.read_only() as conn:
        row = conn.execute("SELECT 1 FROM sets LIMIT 1").fetchone()
    return row is None


def ensure_catalog_populated(
    db: Database,
    *,
    sets_csv: Path,
    themes_csv: Path,
    on_progress: Optional[ProgressCallback] = None,
) -> bool:
    """
    Import the CSV dataset if, and only if, the catalog is currently
    empty -- this is what makes a fresh install work immediately without
    a separate manual build step, while never re-importing (and paying
    that cost again) on every later launch once data is already there.

    ``on_progress``, if given, receives (label, current, total) calls for
    each phase; the caller decides how to display that (an ASCII console
    bar by default, or a GUI progress window -- see
    ``presentation/gui/setup_progress.py``).

    Returns True if an import actually ran, False if the catalog already
    had data. Raises :class:`CatalogDataMissingError` if the catalog is
    empty and the CSV files aren't present to populate it from.
    """
    if not catalog_is_empty(db):
        return False
    if not sets_csv.is_file() or not themes_csv.is_file():
        raise CatalogDataMissingError(sets_csv, themes_csv)
    CsvCatalogImporter(db, sets_csv=sets_csv, themes_csv=themes_csv, on_progress=on_progress).run()
    return True
