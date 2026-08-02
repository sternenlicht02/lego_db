"""
Command language for owned-set modifications entered in the search box.

``lexer`` finds token boundaries, ``parser`` assigns them meaning, and
``executor`` applies a parsed plan against the owned-set repository.
"""

from __future__ import annotations

from lego_db.application.command_language.executor import ModificationResult, apply_modification_plan
from lego_db.application.command_language.parser import ModificationPlan, parse

__all__ = [
    "parse",
    "ModificationPlan",
    "apply_modification_plan",
    "ModificationResult",
]
