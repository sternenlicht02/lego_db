"""
Applies a parsed :class:`ModificationPlan` against the owned repository.

Lexing and parsing above this module know nothing about persistence; this
is the one place in the command language that talks to a repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lego_db.application.command_language.parser import ModificationPlan
from lego_db.application.ports import OwnedRepository
from lego_db.domain.errors import InvalidConditionError, InvalidSetNumberError
from lego_db.domain.value_objects import Condition, SetNumber


@dataclass(frozen=True, slots=True)
class ModificationResult:
    changed: bool
    partial: bool
    malformed: bool = False
    error: Optional[str] = None


def apply_modification_plan(owned_repo: OwnedRepository, plan: ModificationPlan) -> ModificationResult:
    """
    Apply every instruction in ``plan`` as one atomic transaction.

    A malformed or empty plan changes nothing at all: any unrecognized
    fragment anywhere in the original text rejects the whole command,
    rather than silently applying the tokens that happened to parse. This
    mirrors the original app rather than being more "forgiving" about it,
    since a partially-applied command the user didn't ask for is worse
    than an obvious no-op.

    One asymmetry is carried over unchanged too: re-adding a set that is
    already owned is a silent no-op and does not set ``partial`` the way a
    failed remove/condition/note does -- that case was simply never
    flagged as a failure to begin with.
    """
    if not plan.has_tokens or plan.malformed:
        return ModificationResult(changed=False, partial=False, malformed=True)

    changed = False
    partial = False

    try:
        with owned_repo.transaction() as repo:
            for raw_set_num in plan.add:
                try:
                    set_number = SetNumber(raw_set_num)
                except InvalidSetNumberError:
                    partial = True
                    continue
                if not repo.set_exists_in_catalog(set_number):
                    partial = True
                    continue
                if repo.add(set_number):
                    changed = True
                # else: already owned. Deliberately not marked partial.

            for raw_set_num in plan.remove:
                try:
                    set_number = SetNumber(raw_set_num)
                except InvalidSetNumberError:
                    partial = True
                    continue
                if repo.remove(set_number):
                    changed = True
                else:
                    partial = True

            for raw_set_num, code in plan.conditions:
                try:
                    set_number = SetNumber(raw_set_num)
                    condition = Condition.from_code(code)
                except (InvalidSetNumberError, InvalidConditionError):
                    partial = True
                    continue
                if repo.set_condition(set_number, condition):
                    changed = True
                else:
                    partial = True

            for raw_set_num, note_text in plan.notes:
                try:
                    set_number = SetNumber(raw_set_num)
                except InvalidSetNumberError:
                    partial = True
                    continue
                if repo.set_note(set_number, note_text):
                    changed = True
                else:
                    partial = True
    except Exception as exc:  # unexpected infrastructure failure
        return ModificationResult(changed=False, partial=False, malformed=False, error=str(exc))

    return ModificationResult(changed=changed, partial=partial)
