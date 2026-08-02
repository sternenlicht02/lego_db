"""Domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lego_db.domain.value_objects import Condition, SetNumber


@dataclass(frozen=True, slots=True)
class Theme:
    """A LEGO theme, as found in ``themes.csv``."""

    id: int
    name: str
    parent_id: Optional[int] = None


@dataclass(frozen=True, slots=True)
class LegoSet:
    """A LEGO set as defined by the catalog dataset (``sets.csv``)."""

    set_number: SetNumber
    name: str
    year: Optional[int]
    theme_id: Optional[int]
    num_parts: Optional[int]


@dataclass(frozen=True, slots=True)
class OwnedSet:
    """A set the user owns, plus the personal metadata attached to it."""

    set_number: SetNumber
    condition: Condition
    note: Optional[str] = None

    def with_condition(self, condition: Condition) -> "OwnedSet":
        return OwnedSet(set_number=self.set_number, condition=condition, note=self.note)

    def with_note(self, note: Optional[str]) -> "OwnedSet":
        return OwnedSet(set_number=self.set_number, condition=self.condition, note=note)
