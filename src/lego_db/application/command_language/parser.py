"""
Parser for the owned-set modification command language.

Consumes the lexemes produced by ``lexer.scan`` and turns each one into a
concrete instruction (add / remove / set condition / set note, including
the two combined condition+note forms). Token *shape* lives in the lexer;
token *meaning* -- which instruction a token represents, and how to
unescape a note body -- lives here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lego_db.application.command_language.lexer import NOTE_BODY_PATTERN, SETNUM_PATTERN, scan

_ADD_RE = re.compile(rf"^\+({SETNUM_PATTERN})$")
_REMOVE_RE = re.compile(rf"^-({SETNUM_PATTERN})$")
_CONDITION_RE = re.compile(rf"^([012])>({SETNUM_PATTERN})$")
_NOTE_RE = re.compile(rf"^\[({NOTE_BODY_PATTERN})\]>({SETNUM_PATTERN})$")
_COMBINED_RE = re.compile(
    rf"^(?:([012])\[({NOTE_BODY_PATTERN})\]|\[({NOTE_BODY_PATTERN})\]([012]))>({SETNUM_PATTERN})$"
)
_UNESCAPE_RE = re.compile(r"\\(.)")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1F]")


def unescape_note(raw: str) -> str:
    """Resolve ``\\x`` escape pairs in a raw note body to a literal ``x``."""
    return _UNESCAPE_RE.sub(r"\1", raw)


@dataclass
class ModificationPlan:
    add: list[str] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)
    conditions: list[tuple[str, int]] = field(default_factory=list)
    notes: list[tuple[str, str]] = field(default_factory=list)
    # True if the input contained text that isn't one clean sequence of
    # tokens separated by whitespace -- an unrecognized fragment anywhere,
    # or no tokens at all. A malformed plan is rejected in its entirety by
    # the executor, even though the fields above may still hold whatever
    # tokens were individually recognized (useful for tests/diagnostics).
    malformed: bool = False

    @property
    def has_tokens(self) -> bool:
        return bool(self.add or self.remove or self.conditions or self.notes)


def _classify(token_text: str, plan: ModificationPlan) -> None:
    match = _ADD_RE.fullmatch(token_text)
    if match:
        plan.add.append(match.group(1))
        return

    match = _REMOVE_RE.fullmatch(token_text)
    if match:
        plan.remove.append(match.group(1))
        return

    match = _CONDITION_RE.fullmatch(token_text)
    if match:
        plan.conditions.append((match.group(2), int(match.group(1))))
        return

    match = _COMBINED_RE.fullmatch(token_text)
    if match:
        if match.group(1) is not None:
            condition, note = int(match.group(1)), match.group(2)
        else:
            note, condition = match.group(3), int(match.group(4))
        set_num = match.group(5)
        plan.conditions.append((set_num, condition))
        plan.notes.append((set_num, unescape_note(note)))
        return

    match = _NOTE_RE.fullmatch(token_text)
    if match:
        plan.notes.append((match.group(2), unescape_note(match.group(1))))
        return

    # Unreachable as long as this grammar matches the lexer's grammar --
    # kept as a safe fallback rather than an assertion so a future drift
    # between the two degrades to "malformed input" instead of a crash.
    plan.malformed = True


def parse(text: str) -> ModificationPlan:
    """Parse ``text`` into a :class:`ModificationPlan`."""
    plan = ModificationPlan()

    if not text or _CONTROL_CHAR_RE.search(text):
        plan.malformed = True
        return plan

    result = scan(text)

    if not result.lexemes:
        plan.malformed = True
        return plan

    if result.has_unrecognized_text:
        plan.malformed = True

    for lexeme in result.lexemes:
        _classify(lexeme.text, plan)

    return plan
