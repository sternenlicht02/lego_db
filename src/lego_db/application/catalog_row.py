"""
Read-model for the catalog + ownership data shown in the GUI.

The original design used one flat row shape for the main list, the related-sets
list, and the detail dialog alike, and that turned out to be a genuinely
good call rather than something to "properly" split into three near-
identical DTOs: every view of a set (search result, related set, detail
screen) needs the same handful of catalog and ownership fields, just
displayed differently. ``CatalogRow`` keeps that one shape, and stays free
of any UI formatting concerns (those live in the presentation layer).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lego_db.domain.value_objects import Condition


@dataclass(frozen=True, slots=True)
class CatalogRow:
    set_num: str
    parent_theme: str
    theme: str
    name: str
    num_parts: Optional[int]
    year: Optional[int]
    condition: Optional[Condition]
    note: str
