"""
GUI presenter.

The presentation-facing boundary over :class:`CatalogService`. Everything
here is plain Python -- no ``tkinter`` import -- so it is unit-testable
without a display. ``app.py`` and the other modules in this package that
talk to Tk widgets directly all drive this one presenter underneath.
"""

from __future__ import annotations

from typing import Optional

from lego_db.application.catalog_row import CatalogRow
from lego_db.application.command_language.executor import ModificationResult
from lego_db.application.service import CatalogService


class MainPresenter:
    def __init__(self, service: CatalogService) -> None:
        self.service = service
        self.last_search_text: str = ""

    def search(self, text: str) -> list[CatalogRow]:
        self.last_search_text = text.strip()
        return self.service.search(text)

    def refresh_last_search(self) -> list[CatalogRow]:
        """Re-run the most recent search, e.g. after a mutation."""
        return self.service.search(self.last_search_text)

    def related(self, set_num: str) -> list[CatalogRow]:
        return self.service.related(set_num)

    def detail(self, set_num: str) -> Optional[CatalogRow]:
        return self.service.get_detail(set_num)

    def is_owned(self, set_num: str) -> bool:
        return self.service.is_owned(set_num)

    def toggle_owned(self, set_num: str) -> bool:
        return self.service.toggle_owned(set_num)

    def apply_modification(self, text: str) -> ModificationResult:
        return self.service.apply_modification(text)
