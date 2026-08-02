"""
Application layer.

Orchestrates the domain model on behalf of the presentation layer: the
catalog/owned-set service, the command language, and the repository ports
they depend on. Nothing here imports sqlite3, tkinter, or csv directly --
those belong to infrastructure and presentation.
"""

from __future__ import annotations

from lego_db.application.catalog_row import CatalogRow
from lego_db.application.ports import CatalogRepository, OwnedRepository
from lego_db.application.service import CatalogService

__all__ = [
    "CatalogRow",
    "CatalogRepository",
    "OwnedRepository",
    "CatalogService",
]
