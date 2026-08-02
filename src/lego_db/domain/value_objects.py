"""
Domain value objects.

SetNumber and Condition are the two pieces of data in this application that
carry real parsing/validation rules, so both live here rather than being
treated as bare strings or ints scattered across the codebase.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar, Optional

from lego_db.domain.errors import InvalidConditionError, InvalidSetNumberError

# A set number, as it appears verbatim in the Rebrickable ``sets.csv`` export,
# is built only from ASCII letters, digits, '.' and '-'. Real-world examples
# include "10013-1", "100STORES-1", "201908-mmb", "10213sup-1",
# "1308-1-DBASE-1" and "214.10-1" -- so letters, dots, and more than one '-'
# must all be accepted.
_CHARSET_RE = re.compile(r"^[0-9A-Za-z.\-]+$")

# A run of one or more ASCII digits, used both to test the text following the
# last '-' and to build a natural sort key over the whole set number.
_ALL_DIGITS_RE = re.compile(r"^[0-9]+$")

# Splits a string into alternating digit-runs and non-digit-runs, e.g.
# "100STORES-1" -> ["100", "STORES-", "1"].
_CHUNK_RE = re.compile(r"[0-9]+|[^0-9]+")


@dataclass(frozen=True, slots=True)
class SetNumber:
    """
    Canonical representation of a LEGO set number.

    The value is stored and compared exactly as it appears in the catalog
    (``sets.csv`` / the ``sets`` table). ``base`` and ``variant`` are derived
    views used for grouping and natural sorting; they are not stored
    separately anywhere -- both are cheap to recompute from ``value``.

    Normalization rule (fixed by the project's data format, not a style
    choice): look at the text after the *last* '-' in the set number. If
    that text is made up only of the digits 0-9, the set number's "base"
    (전반부) is everything before that last '-', and its "variant" (후반부)
    is the digits read as an int. Otherwise there is no variant, and the
    base is the whole set number.
    """

    value: str

    _CHARSET_RE: ClassVar[re.Pattern[str]] = _CHARSET_RE

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidSetNumberError(self.value)
        candidate = self.value.strip()
        if not candidate or not self._CHARSET_RE.fullmatch(candidate):
            raise InvalidSetNumberError(self.value)
        object.__setattr__(self, "value", candidate)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"SetNumber({self.value!r})"

    @property
    def base(self) -> str:
        """The "전반부": the set number with any trailing "-<digits>" removed."""
        split_index = self.value.rfind("-")
        if split_index == -1:
            return self.value
        suffix = self.value[split_index + 1:]
        if suffix and _ALL_DIGITS_RE.fullmatch(suffix):
            return self.value[:split_index]
        return self.value

    @property
    def variant(self) -> Optional[int]:
        """The "후반부": the trailing digits after the last '-', if any."""
        split_index = self.value.rfind("-")
        if split_index == -1:
            return None
        suffix = self.value[split_index + 1:]
        if suffix and _ALL_DIGITS_RE.fullmatch(suffix):
            return int(suffix)
        return None

    @property
    def sort_key(self) -> tuple:
        """
        A natural sort key over the raw value.

        Digit runs compare as integers and everything else compares as
        case-folded text, so "20-1" sorts before "100-1" and
        "100STORES-1" sorts near other "100..." sets instead of being
        pushed to the end of the list -- unlike a plain numeric-prefix
        sort, this also produces a stable, sensible order for set numbers
        that are not purely numeric.
        """
        chunks = []
        for chunk in _CHUNK_RE.findall(self.value):
            if _ALL_DIGITS_RE.fullmatch(chunk):
                chunks.append((0, int(chunk)))
            else:
                chunks.append((1, chunk.casefold()))
        return tuple(chunks)


class Condition(IntEnum):
    """
    Condition of an owned set.

    Only three states are meaningful anywhere in this application: the
    default (unspecified) state, a "bad" state, and a "good" state. There is
    deliberately no fourth "missing parts" state -- nothing in the GUI,
    command language, or export format ever produces or consumes one, so
    keeping it would just be unused state space.
    """

    DEFAULT = 0
    BAD = 1
    GOOD = 2

    def __str__(self) -> str:
        # Explicit override: don't depend on how a given Python version
        # formats IntEnum members. The wire format is always the bare digit.
        return str(int(self))

    @classmethod
    def from_code(cls, value: object) -> "Condition":
        try:
            code = int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise InvalidConditionError(value) from exc
        try:
            return cls(code)
        except ValueError as exc:
            raise InvalidConditionError(value) from exc

    @property
    def tag(self) -> str:
        """Treeview tag name used to color a row by condition."""
        return _CONDITION_TAGS[self]


_CONDITION_TAGS: dict[Condition, str] = {
    Condition.DEFAULT: "owned",
    Condition.BAD: "bad",
    Condition.GOOD: "good",
}
