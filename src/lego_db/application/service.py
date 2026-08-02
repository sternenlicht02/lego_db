"""
Application service.

A single, small facade over the two repository ports. It owns exactly the
bits of orchestration that don't belong in either the domain model or a
repository: dispatching "owned" / "보유" searches to the owned list instead
of the catalog, and wiring the command language up to the owned repository.
"""

from __future__ import annotations

from typing import Optional

from lego_db.application.catalog_row import CatalogRow
from lego_db.application.command_language.executor import ModificationResult, apply_modification_plan
from lego_db.application.command_language.parser import parse
from lego_db.application.ports import CatalogRepository, OwnedRepository
from lego_db.domain.errors import InvalidSetNumberError
from lego_db.domain.value_objects import Condition, SetNumber

# Deliberately kept as plain hardcoded text (not translated): this one search keyword is
# hardcoded in English and Korean rather than translated, same as the
# command language's punctuation-based syntax is not translated either.
_OWNED_KEYWORDS = {"owned", "보유"}
_VALID_CONDITION_TOKENS = {"0", "1", "2"}


class CatalogService:
    def __init__(self, catalog_repo: CatalogRepository, owned_repo: OwnedRepository) -> None:
        self.catalog_repo = catalog_repo
        self.owned_repo = owned_repo

    def search(self, text: str) -> list[CatalogRow]:
        """
        Interpret the search box's text.

        An empty query lists every catalog set. A query starting with
        "owned"/"보유" lists owned sets, optionally filtered by condition
        (a second word that must be exactly "0", "1", or "2"). Anything
        else is a plain set-number prefix search.
        """
        query = text.strip()
        if not query:
            return list(self.catalog_repo.search_by_prefix(""))

        head = query.split(maxsplit=1)[0].casefold()
        if head in _OWNED_KEYWORDS:
            parts = query.split()
            condition_token = parts[1] if len(parts) > 1 else None
            return self.list_owned(condition_token)

        return list(self.catalog_repo.search_by_prefix(query))

    def list_owned(self, condition_token: Optional[str] = None) -> list[CatalogRow]:
        if condition_token is None:
            return list(self.owned_repo.list(None))
        if condition_token not in _VALID_CONDITION_TOKENS:
            return []
        return list(self.owned_repo.list(Condition.from_code(condition_token)))

    def get_detail(self, raw_set_num: str) -> Optional[CatalogRow]:
        set_number = self._try_parse(raw_set_num)
        if set_number is None:
            return None
        return self.catalog_repo.get(set_number)

    def related(self, raw_set_num: str) -> list[CatalogRow]:
        set_number = self._try_parse(raw_set_num)
        if set_number is None:
            return []
        return list(self.catalog_repo.related(set_number))

    def is_owned(self, raw_set_num: str) -> bool:
        set_number = self._try_parse(raw_set_num)
        if set_number is None:
            return False
        return self.owned_repo.is_owned(set_number)

    def toggle_owned(self, raw_set_num: str) -> bool:
        """Add if not owned, remove if owned. The set number must exist already."""
        return self.owned_repo.toggle(SetNumber(raw_set_num))

    def apply_modification(self, text: str) -> ModificationResult:
        plan = parse(text)
        return apply_modification_plan(self.owned_repo, plan)

    @staticmethod
    def _try_parse(raw_set_num: str) -> Optional[SetNumber]:
        try:
            return SetNumber(raw_set_num)
        except InvalidSetNumberError:
            return None
