from __future__ import annotations

import unittest

import conftest  # noqa: F401  (adds src/ to sys.path)

from lego_db.domain.errors import InvalidConditionError, InvalidSetNumberError
from lego_db.domain.value_objects import Condition, SetNumber


class SetNumberConstructionTests(unittest.TestCase):
    def test_accepts_plain_numeric_form(self) -> None:
        self.assertEqual(str(SetNumber("10221-1")), "10221-1")

    def test_trims_surrounding_whitespace(self) -> None:
        self.assertEqual(str(SetNumber("  10221-1  ")), "10221-1")

    def test_accepts_letters_dots_and_multiple_dashes(self) -> None:
        for raw in ["100STORES-1", "201908-mmb", "10213sup-1", "1308-1-DBASE-1", "214.10-1"]:
            with self.subTest(raw=raw):
                self.assertEqual(str(SetNumber(raw)), raw)

    def test_rejects_empty_string(self) -> None:
        with self.assertRaises(InvalidSetNumberError):
            SetNumber("")

    def test_rejects_disallowed_characters(self) -> None:
        for bad in ["1234_1", "1234 1", "1234/1", "1234#1", "가나다"]:
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidSetNumberError):
                    SetNumber(bad)

    def test_equality_and_hash_are_value_based(self) -> None:
        self.assertEqual(SetNumber("1234-1"), SetNumber("1234-1"))
        self.assertEqual(len({SetNumber("1234-1"), SetNumber("1234-1")}), 1)


class SetNumberNormalizationTests(unittest.TestCase):
    """
    The exact examples given in the spec, verified independently against
    the real Rebrickable dataset before being written here as regression
    tests (see the design notes for how each was checked).
    """

    CASES = [
        ("0003977811-1", "0003977811", 1),
        ("10013-1", "10013", 1),
        ("41775-12", "41775", 12),
        ("100STORES-1", "100STORES", 1),
        ("201908-mmb", "201908-mmb", None),
        ("10213sup-1", "10213sup", 1),
        ("1308-1-DBASE-1", "1308-1-DBASE", 1),
        ("214.10-1", "214.10", 1),
    ]

    def test_base_and_variant_normalization(self) -> None:
        for raw, expected_base, expected_variant in self.CASES:
            with self.subTest(raw=raw):
                number = SetNumber(raw)
                self.assertEqual(number.base, expected_base)
                self.assertEqual(number.variant, expected_variant)

    def test_no_dash_means_no_variant(self) -> None:
        number = SetNumber("ABC123")
        self.assertEqual(number.base, "ABC123")
        self.assertIsNone(number.variant)

    def test_trailing_dash_with_no_digits_after_it_has_no_variant(self) -> None:
        number = SetNumber("FOO-BAR")
        self.assertEqual(number.base, "FOO-BAR")
        self.assertIsNone(number.variant)


class SetNumberSortKeyTests(unittest.TestCase):
    def test_orders_numeric_bases_by_value_not_lexically(self) -> None:
        numbers = [SetNumber("100-1"), SetNumber("20-1"), SetNumber("9-1")]
        ordered = sorted(numbers, key=lambda n: n.sort_key)
        self.assertEqual([str(n) for n in ordered], ["9-1", "20-1", "100-1"])

    def test_orders_variants_within_the_same_base_numerically(self) -> None:
        numbers = [SetNumber("71022-10"), SetNumber("71022-2"), SetNumber("71022-1")]
        ordered = sorted(numbers, key=lambda n: n.sort_key)
        self.assertEqual([str(n) for n in ordered], ["71022-1", "71022-2", "71022-10"])

    def test_handles_mixed_alnum_bases_stably(self) -> None:
        numbers = [SetNumber("100STORES-1"), SetNumber("20-1"), SetNumber("100-1")]
        ordered = sorted(numbers, key=lambda n: n.sort_key)
        self.assertEqual(str(ordered[0]), "20-1")
        self.assertEqual({str(n) for n in ordered[1:]}, {"100-1", "100STORES-1"})


class ConditionTests(unittest.TestCase):
    def test_from_code_accepts_valid_codes(self) -> None:
        for code in [0, 1, 2, "0", "1", "2", " 2 "]:
            with self.subTest(code=code):
                condition = Condition.from_code(code)
                self.assertEqual(str(condition), str(int(str(code).strip())))

    def test_str_is_bare_digit(self) -> None:
        self.assertEqual(str(Condition.DEFAULT), "0")
        self.assertEqual(str(Condition.BAD), "1")
        self.assertEqual(str(Condition.GOOD), "2")

    def test_tag_matches_legacy_names(self) -> None:
        self.assertEqual(Condition.DEFAULT.tag, "owned")
        self.assertEqual(Condition.BAD.tag, "bad")
        self.assertEqual(Condition.GOOD.tag, "good")

    def test_from_code_rejects_invalid_codes(self) -> None:
        for bad_code in [3, -1, "missing_parts", "new", "", None]:
            with self.subTest(bad_code=bad_code):
                with self.assertRaises(InvalidConditionError):
                    Condition.from_code(bad_code)


if __name__ == "__main__":
    unittest.main()
