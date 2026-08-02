"""
Owned-set import (restore from backup).

Restores the owned-set inventory from the most recent
``owned_<yymmdd>.txt`` file found in the instance export directory. Any
file not matching that exact pattern is not considered a backup at all.

The restore runs as one atomic transaction: existing owned-set rows are
cleared and every token from the backup is applied within that same
transaction. If anything fails partway through -- a locked database, an
unexpected error applying some token -- the whole transaction rolls back
and the original inventory is left exactly as it was, rather than ending
up cleared with only some of the backup re-applied.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from lego_db.application.command_language.executor import ModificationResult, apply_modification_plan
from lego_db.application.command_language.parser import parse
from lego_db.application.ports import OwnedRepository

_BACKUP_FILENAME_RE = re.compile(r"^owned_(\d{6})\.txt$")


def find_latest_backup_file(export_dir: Path) -> Optional[Path]:
    """
    The most recent ``owned_<yymmdd>.txt`` file in ``export_dir`` (by the
    date encoded in its name), or None if there isn't one.
    """
    if not export_dir.is_dir():
        return None

    candidates: list[tuple[str, Path]] = []
    for path in export_dir.iterdir():
        if not path.is_file():
            continue
        match = _BACKUP_FILENAME_RE.match(path.name)
        if match:
            candidates.append((match.group(1), path))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def import_owned_sets(owned_repo: OwnedRepository, export_dir: Path) -> ModificationResult:
    txt_path = find_latest_backup_file(export_dir)
    if txt_path is None:
        raise FileNotFoundError(f"no owned_<yymmdd>.txt backup file found in {export_dir}")

    text = txt_path.read_text(encoding="utf-8")
    plan = parse(text)
    if not plan.has_tokens or plan.malformed:
        return ModificationResult(changed=False, partial=False, malformed=True)

    with owned_repo.transaction() as repo:
        repo.clear_all()
        # apply_modification_plan opens its own `with repo.transaction():`,
        # which detects that one is already active (see
        # SQLiteOwnedRepository.transaction) and joins it instead of
        # starting a second one -- so the clear above and every token
        # below commit or roll back together.
        result = apply_modification_plan(repo, plan)
        if result.error is not None:
            # apply_modification_plan reports infrastructure failures as
            # a result value instead of a raised exception (so a single
            # bad command from the search box doesn't crash the GUI).
            # For a restore, that failure must reach this `with` block as
            # a real exception, or this transaction would see no error at
            # all and commit the clear above without the data it was
            # supposed to restore alongside it.
            raise RuntimeError(result.error)
        return result
