"""
Owned-set export.

Writes two files under the instance export directory:

- ``owned_<yymmdd>.txt``: a whitespace-separated stream of modification
  tokens -- the same command language the search box accepts -- so the
  file doubles as a script that can reconstruct the owned-set inventory
  (see ``importers.py``, or paste it directly into the search box).
- ``owned_<yymmdd>.csv``: a spreadsheet-friendly export with localized
  headers matching the GUI's columns.

``yymmdd`` is the date the owned list was last added to (the most recent
set added, not the date the export itself runs), so the filename reflects
how current the collection data is, not when a copy happened to be made.
If nothing is owned yet, today's date is used instead.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from lego_db.application.ports import OwnedRepository
from lego_db.i18n.service import t


def _escape_note(text: str) -> str:
    return text.replace("\\", "\\\\").replace("]", "\\]")


def _build_command_tokens(rows) -> list[str]:
    tokens: list[str] = []
    for row in rows:
        tokens.append(f"+{row.set_num}")

        condition_code = int(row.condition) if row.condition is not None else None
        note = row.note or ""
        has_condition = condition_code in (1, 2)
        has_note = bool(note)

        if has_condition and has_note:
            tokens.append(f"{condition_code}[{_escape_note(note)}]>{row.set_num}")
        elif has_condition:
            tokens.append(f"{condition_code}>{row.set_num}")
        elif has_note:
            tokens.append(f"[{_escape_note(note)}]>{row.set_num}")

    return tokens


def export_filename_stem(owned_repo: OwnedRepository) -> str:
    """``owned_<yymmdd>``, where yymmdd is the last-added date (see module docstring)."""
    reference_date = owned_repo.last_added_date() or date.today()
    return f"owned_{reference_date:%y%m%d}"


def export_owned_sets(owned_repo: OwnedRepository, export_dir: Path) -> tuple[Path, Path]:
    """Write the TXT and CSV exports into ``export_dir``. Returns their paths."""
    export_dir.mkdir(parents=True, exist_ok=True)
    stem = export_filename_stem(owned_repo)
    txt_path = export_dir / f"{stem}.txt"
    csv_path = export_dir / f"{stem}.csv"

    rows = owned_repo.list()

    txt_path.write_text(" ".join(_build_command_tokens(rows)), encoding="utf-8")

    headers = [
        t("parent_theme"), t("theme"), t("set_num"), t("name"),
        t("pieces"), t("release"), t("condition"), t("note"),
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(
                [
                    row.parent_theme,
                    row.theme,
                    row.set_num,
                    row.name,
                    row.num_parts if row.num_parts is not None else "",
                    row.year if row.year is not None else "",
                    str(row.condition) if row.condition is not None else "-",
                    row.note or "",
                ]
            )

    return txt_path, csv_path
