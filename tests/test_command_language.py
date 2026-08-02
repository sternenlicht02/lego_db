from __future__ import annotations

import unittest

import conftest  # noqa: F401  (adds src/ to sys.path)

from lego_db.application.command_language.lexer import scan
from lego_db.application.command_language.parser import parse, unescape_note


class ScanTests(unittest.TestCase):
    def test_finds_all_token_kinds(self) -> None:
        result = scan(r"+123-4 -567 2>890-1 [a\]b]>42")
        self.assertFalse(result.has_unrecognized_text)
        self.assertEqual(
            [lex.text for lex in result.lexemes],
            [r"+123-4", "-567", "2>890-1", r"[a\]b]>42"],
        )

    def test_reports_gap_between_tokens(self) -> None:
        result = scan("abc +1")
        self.assertTrue(result.has_unrecognized_text)
        self.assertEqual([lex.text for lex in result.lexemes], ["+1"])

    def test_empty_text_has_no_lexemes(self) -> None:
        result = scan("")
        self.assertEqual(result.lexemes, ())

    def test_accepts_alphanumeric_set_numbers(self) -> None:
        result = scan("+100STORES-1 -201908-mmb 2>10213sup-1 [gift]>1308-1-DBASE-1")
        self.assertFalse(result.has_unrecognized_text)
        self.assertEqual(len(result.lexemes), 4)


class ParseBasicTests(unittest.TestCase):
    def test_parses_full_example(self) -> None:
        plan = parse(r"+123-4 -567 2>890-1 [a\]b]>42")
        self.assertTrue(plan.has_tokens)
        self.assertFalse(plan.malformed)
        self.assertEqual(plan.add, ["123-4"])
        self.assertEqual(plan.remove, ["567"])
        self.assertEqual(plan.conditions, [("890-1", 2)])
        self.assertEqual(plan.notes, [("42", "a]b")])

    def test_malformed_gap_still_records_recognized_tokens(self) -> None:
        plan = parse("abc +1")
        self.assertTrue(plan.has_tokens)
        self.assertTrue(plan.malformed)
        self.assertEqual(plan.add, ["1"])

    def test_empty_text_is_malformed(self) -> None:
        plan = parse("")
        self.assertFalse(plan.has_tokens)
        self.assertTrue(plan.malformed)

    def test_control_characters_anywhere_make_the_whole_input_malformed(self) -> None:
        plan = parse("+1234-1\n-5678-1")
        self.assertTrue(plan.malformed)
        self.assertFalse(plan.has_tokens)

    def test_multiple_commands_combined(self) -> None:
        plan = parse("+1234-1 -5678-1 2[gift]>1111-1")
        self.assertFalse(plan.malformed)
        self.assertEqual(plan.add, ["1234-1"])
        self.assertEqual(plan.remove, ["5678-1"])
        self.assertEqual(plan.conditions, [("1111-1", 2)])
        self.assertEqual(plan.notes, [("1111-1", "gift")])


class ParseAlphanumericSetNumberTests(unittest.TestCase):
    """
    The command language must accept the same wide variety of set number
    formats the catalog itself contains, not just plain digits.
    """

    def test_add_and_remove_accept_letters_dots_and_multiple_dashes(self) -> None:
        for raw in ["100STORES-1", "201908-mmb", "10213sup-1", "1308-1-DBASE-1", "214.10-1"]:
            with self.subTest(raw=raw):
                plan = parse(f"+{raw}")
                self.assertFalse(plan.malformed)
                self.assertEqual(plan.add, [raw])

                plan = parse(f"-{raw}")
                self.assertFalse(plan.malformed)
                self.assertEqual(plan.remove, [raw])

    def test_condition_and_note_accept_alphanumeric_targets(self) -> None:
        plan = parse("2>100STORES-1")
        self.assertFalse(plan.malformed)
        self.assertEqual(plan.conditions, [("100STORES-1", 2)])

        plan = parse("[gift]>1308-1-DBASE-1")
        self.assertFalse(plan.malformed)
        self.assertEqual(plan.notes, [("1308-1-DBASE-1", "gift")])

    def test_combined_forms_accept_alphanumeric_targets(self) -> None:
        plan = parse("1[note]>10213sup-1")
        self.assertEqual(plan.conditions, [("10213sup-1", 1)])
        self.assertEqual(plan.notes, [("10213sup-1", "note")])

        plan = parse("[note]1>10213sup-1")
        self.assertEqual(plan.conditions, [("10213sup-1", 1)])
        self.assertEqual(plan.notes, [("10213sup-1", "note")])


class NoteEscapingTests(unittest.TestCase):
    """
    These cases were checked against the legacy regex directly (not just
    against its documentation, which turned out to have a couple of
    stale/incorrect examples -- see the accompanying design notes) so the
    exact escaping semantics carry over unchanged.
    """

    def test_escaped_bracket(self) -> None:
        plan = parse(r"[\]]>1234-1")
        self.assertFalse(plan.malformed)
        self.assertEqual(plan.notes, [("1234-1", "]")])

    def test_lone_trailing_backslash_before_closing_bracket(self) -> None:
        # A single backslash immediately before ']' resolves, via normal
        # backtracking, to a note body that is just that one backslash.
        plan = parse(r"[\]>1234-1")
        self.assertFalse(plan.malformed)
        self.assertEqual(plan.notes, [("1234-1", "\\")])

    def test_escaped_backslash_then_literal_text(self) -> None:
        plan = parse(r"[a\\b]>1234-1")
        self.assertFalse(plan.malformed)
        self.assertEqual(plan.notes, [("1234-1", "a\\b")])

    def test_escaped_letter_drops_the_backslash(self) -> None:
        # Escaping a character that isn't ']' or '\' still consumes the
        # backslash -- there is nothing special about letters here.
        plan = parse(r"[a\b]>1234-1")
        self.assertFalse(plan.malformed)
        self.assertEqual(plan.notes, [("1234-1", "ab")])

    def test_unescape_note_helper(self) -> None:
        self.assertEqual(unescape_note(r"a\]b"), "a]b")
        self.assertEqual(unescape_note("\\"), "\\")


if __name__ == "__main__":
    unittest.main()
