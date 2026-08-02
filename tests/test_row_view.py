from __future__ import annotations

import unittest

import conftest  # noqa: F401  (adds src/ to sys.path)

from lego_db.application.catalog_row import CatalogRow
from lego_db.domain.value_objects import Condition
from lego_db.presentation.gui.row_view import (
    condition_display,
    condition_tag,
    format_copy_text,
    main_row_values,
    related_row_values,
)


def _row(**overrides) -> CatalogRow:
    base = dict(
        set_num="75192-1",
        parent_theme="Star Wars",
        theme="Ultimate Collector Series",
        name="Millennium Falcon",
        num_parts=7541,
        year=2017,
        condition=None,
        note="",
    )
    base.update(overrides)
    return CatalogRow(**base)


class ConditionDisplayTests(unittest.TestCase):
    def test_not_owned_shows_dash(self) -> None:
        self.assertEqual(condition_display(_row(condition=None)), "-")
        self.assertEqual(condition_tag(_row(condition=None)), "")

    def test_owned_shows_digit_and_tag(self) -> None:
        self.assertEqual(condition_display(_row(condition=Condition.GOOD)), "2")
        self.assertEqual(condition_tag(_row(condition=Condition.GOOD)), "good")
        self.assertEqual(condition_tag(_row(condition=Condition.BAD)), "bad")
        self.assertEqual(condition_tag(_row(condition=Condition.DEFAULT)), "owned")


class RowValuesTests(unittest.TestCase):
    def test_main_row_values_order_and_blanks(self) -> None:
        row = _row(num_parts=None, year=None, note=None)
        values = main_row_values(row)
        self.assertEqual(
            values,
            ("Star Wars", "Ultimate Collector Series", "75192-1", "Millennium Falcon", "", "", "-", ""),
        )

    def test_related_row_values(self) -> None:
        row = _row(condition=Condition.BAD)
        self.assertEqual(related_row_values(row), ("75192-1", "Millennium Falcon", 7541, "1"))


class FormatCopyTextTests(unittest.TestCase):
    def test_without_normalization_keeps_full_set_number(self) -> None:
        text = format_copy_text(_row(), normalize=False)
        self.assertEqual(text, "Star Wars Ultimate Collector Series 75192-1 Millennium Falcon, 7541pc, 2017")

    def test_with_normalization_strips_variant_suffix(self) -> None:
        text = format_copy_text(_row(set_num="1308-1-DBASE-1"), normalize=True)
        self.assertIn("1308-1-DBASE ", text)
        self.assertNotIn("1308-1-DBASE-1", text)

    def test_missing_fields_collapse_gracefully(self) -> None:
        text = format_copy_text(_row(parent_theme="", num_parts=None, year=None), normalize=False)
        self.assertEqual(text, "Ultimate Collector Series 75192-1 Millennium Falcon, pc,")


if __name__ == "__main__":
    unittest.main()
