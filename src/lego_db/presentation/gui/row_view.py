"""
View-formatting helpers.

Pure functions that turn a :class:`CatalogRow` into the tuples and strings
the tree/detail widgets need. Nothing here imports ``tkinter``, so these
are unit-testable without a display.
"""

from __future__ import annotations

from lego_db.application.catalog_row import CatalogRow
from lego_db.domain.value_objects import SetNumber

MAIN_COLUMNS = ("parent_theme", "theme", "set_num", "name", "pieces", "year", "condition", "note")
RELATED_COLUMNS = ("set_num", "name", "pieces", "condition")

# Tag -> background color, used by every tree the app renders, so
# that "what does this color mean" stays a single answer across the app.
CONDITION_TAG_COLORS = {
    "owned": "#EAF6FF",  # condition 0 (default)
    "bad": "#ffe4e6",    # condition 1
    "good": "#eaffea",   # condition 2
}


def condition_display(row: CatalogRow) -> str:
    return str(row.condition) if row.condition is not None else "-"


def condition_tag(row: CatalogRow) -> str:
    return row.condition.tag if row.condition is not None else ""


def main_row_values(row: CatalogRow) -> tuple:
    return (
        row.parent_theme,
        row.theme,
        row.set_num,
        row.name,
        row.num_parts if row.num_parts is not None else "",
        row.year if row.year is not None else "",
        condition_display(row),
        row.note or "",
    )


def related_row_values(row: CatalogRow) -> tuple:
    return (
        row.set_num,
        row.name,
        row.num_parts if row.num_parts is not None else "",
        condition_display(row),
    )


def format_copy_text(row: CatalogRow, *, normalize: bool) -> str:
    """
    ``<parent_theme> <theme> <set_num> <name>, <pieces>pc, <year>``

    When ``normalize`` is set, the set number is reduced to its base (the
    "전반부"): the same rule used to group variants of a set together
    elsewhere in the app, applied here to the clipboard text too instead
    of a second, separate normalization rule.
    """
    set_num = SetNumber(row.set_num).base if normalize else row.set_num
    parent_theme = row.parent_theme or ""
    theme = row.theme or ""
    pieces = "" if row.num_parts is None else str(row.num_parts)
    year = "" if row.year is None else str(row.year)
    return f"{parent_theme} {theme} {set_num} {row.name}, {pieces}pc, {year}".strip()
