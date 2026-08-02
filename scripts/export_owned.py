#!/usr/bin/env python3
"""
Export owned sets to ``instance/exports/owned_<yymmdd>.txt`` and ``.csv``,
where ``yymmdd`` is the date the owned list was last added to.

Usage:
    python scripts/export_owned.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lego_db.i18n.service import load_config, set_language  # noqa: E402
from lego_db.infrastructure.database import Database  # noqa: E402
from lego_db.infrastructure.exporters import export_owned_sets  # noqa: E402
from lego_db.infrastructure.repositories import SQLiteOwnedRepository  # noqa: E402
from lego_db.infrastructure.schema import initialize_schema  # noqa: E402
from lego_db.paths import database_path, export_dir  # noqa: E402


def main() -> None:
    config = load_config()
    set_language(str(config.get("language", "en")))

    db = Database(database_path())
    initialize_schema(db)
    owned_repo = SQLiteOwnedRepository(db)

    txt_path, csv_path = export_owned_sets(owned_repo, export_dir())

    print(f"Exported TXT: {txt_path}")
    print(f"Exported CSV: {csv_path}")


if __name__ == "__main__":
    main()
