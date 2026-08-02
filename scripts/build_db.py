#!/usr/bin/env python3
"""
Build (or update) the local SQLite catalog from ``sets.csv`` / ``themes.csv``.

Usage:
    python scripts/build_db.py
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lego_db.infrastructure.csv_import import CsvCatalogImporter  # noqa: E402
from lego_db.infrastructure.database import Database  # noqa: E402
from lego_db.paths import csv_data_dir, database_path  # noqa: E402

_LOGGER = logging.getLogger("build_db")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    db_path = database_path()
    mode = "Updating" if db_path.exists() else "Building"
    _LOGGER.info("%s catalog at %s", mode, db_path)

    db = Database(db_path)
    importer = CsvCatalogImporter(
        db,
        sets_csv=csv_data_dir() / "sets.csv",
        themes_csv=csv_data_dir() / "themes.csv",
    )

    start = time.perf_counter()
    try:
        themes_summary, sets_summary = importer.run()
    except FileNotFoundError as exc:
        _LOGGER.error("%s", exc)
        _LOGGER.error(
            "Download sets.csv and themes.csv from https://rebrickable.com/downloads/ "
            "and place them in %s",
            csv_data_dir(),
        )
        raise SystemExit(1) from exc
    elapsed = time.perf_counter() - start

    _LOGGER.info(
        "Imported %d/%d rows from %s (skipped %d)",
        themes_summary.imported_rows,
        themes_summary.total_rows,
        themes_summary.source,
        themes_summary.skipped_rows,
    )
    _LOGGER.info(
        "Imported %d/%d rows from %s (skipped %d)",
        sets_summary.imported_rows,
        sets_summary.total_rows,
        sets_summary.source,
        sets_summary.skipped_rows,
    )
    _LOGGER.info("Total time: %.2f seconds", elapsed)


if __name__ == "__main__":
    main()
