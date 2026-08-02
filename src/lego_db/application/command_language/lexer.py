"""
Lexer for the owned-set modification command language.

The search box doubles as a small command line: typing things like
``+1234-1``, ``-1234-1``, ``2>1234-1`` or ``[a note]>1234-1`` (and the two
combined condition+note forms) mutates the owned-set inventory instead of
searching. This module only finds *where* those commands are in a longer
string; it does not know what any of them mean. See ``parser.py`` for that.

Splitting the two concerns this way (rather than one large ad hoc regex
tangled up with the code that acts on it) is what makes it practical to
extend the grammar later or reuse it outside this project: adding a new
kind of token only means adding one alternative here and one branch in the
parser, and both halves can be tested independently of the GUI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A raw catalog set number is built only from ASCII letters, digits, '.'
# and '-' -- see lego_db.domain.value_objects.SetNumber for the full
# normalization rules that apply once a number has been extracted.
SETNUM_PATTERN = r"[0-9A-Za-z.\-]+"

# The body of a [...] note: either an escaped pair (backslash followed by
# any one character) or any character other than an unescaped ']'.
# Because the two alternatives overlap on a lone backslash, standard regex
# backtracking is what makes `[\]>1234-1` resolve to a note body of a
# single backslash rather than failing to match -- this is existing,
# user-visible behavior, so the pattern is kept exactly as-is rather than
# "cleaned up".
NOTE_BODY_PATTERN = r"(?:\\.|[^\]])*"

# Every syntactically valid token, used only to find token boundaries.
_TOKEN_RE = re.compile(
    rf"\[{NOTE_BODY_PATTERN}\]>{SETNUM_PATTERN}"  # [note]>setnum
    rf"|[012]\[{NOTE_BODY_PATTERN}\]>{SETNUM_PATTERN}"  # 2[note]>setnum
    rf"|\[{NOTE_BODY_PATTERN}\][012]>{SETNUM_PATTERN}"  # [note]2>setnum
    rf"|\+{SETNUM_PATTERN}"  # +setnum
    rf"|-{SETNUM_PATTERN}"  # -setnum
    rf"|[012]>{SETNUM_PATTERN}"  # 2>setnum
)


@dataclass(frozen=True, slots=True)
class Lexeme:
    """A span of text that matches the token grammar, verbatim."""

    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ScanResult:
    lexemes: tuple[Lexeme, ...]
    # True if any non-whitespace text falls outside every lexeme found
    # (before the first one, between two of them, or after the last one).
    has_unrecognized_text: bool


def scan(text: str) -> ScanResult:
    """Find every command-token-shaped span in ``text``."""
    lexemes: list[Lexeme] = []
    cursor = 0
    has_unrecognized_text = False

    for match in _TOKEN_RE.finditer(text):
        gap = text[cursor:match.start()]
        if gap.strip():
            has_unrecognized_text = True
        lexemes.append(Lexeme(text=match.group(0), start=match.start(), end=match.end()))
        cursor = match.end()

    if text[cursor:].strip():
        has_unrecognized_text = True

    return ScanResult(lexemes=tuple(lexemes), has_unrecognized_text=has_unrecognized_text)
