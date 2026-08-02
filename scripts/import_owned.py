#!/usr/bin/env python3
"""
Restore owned sets from the most recent ``instance/exports/owned_<yymmdd>.txt``.

The restore is atomic: either the whole backup applies, or nothing
changes at all (see ``lego_db.infrastructure.importers`` for details).

Usage:
    python scripts/import_owned.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lego_db.infrastructure.database import Database  # noqa: E402
from lego_db.infrastructure.importers import import_owned_sets  # noqa: E402
from lego_db.infrastructure.repositories import SQLiteOwnedRepository  # noqa: E402
from lego_db.infrastructure.schema import initialize_schema  # noqa: E402
from lego_db.paths import database_path, export_dir  # noqa: E402


def main() -> None:
    db = Database(database_path())
    initialize_schema(db)
    owned_repo = SQLiteOwnedRepository(db)

    try:
        result = import_owned_sets(owned_repo, export_dir())
    except FileNotFoundError as exc:
        print(f"Backup file not found: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        print(f"Restore failed, nothing was changed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if result.malformed:
        print("Backup file is empty or unreadable as a command list; nothing was changed.", file=sys.stderr)
        raise SystemExit(1)

    if result.partial:
        print("Restore complete, but some entries could not be applied (see above for a full re-export).")
    else:
        print("Restore complete.")


if __name__ == "__main__":
    main()
