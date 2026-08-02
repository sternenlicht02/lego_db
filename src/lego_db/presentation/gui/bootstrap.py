"""
Shared GUI startup sequence.

Handles the first-run language dialog, making sure the catalog actually
has data in it (showing a setup progress window while that happens, if
it's needed at all), the fade-in show of the main window, and starting
the mainloop.
"""

from __future__ import annotations

import tkinter as tk
from contextlib import suppress
from typing import Callable, Protocol

from lego_db.application.service import CatalogService
from lego_db.i18n.service import language_options_from_files, load_config, set_language, write_config
from lego_db.infrastructure.csv_import import CatalogDataMissingError, catalog_is_empty, ensure_catalog_populated
from lego_db.infrastructure.database import Database
from lego_db.infrastructure.repositories import SQLiteCatalogRepository, SQLiteOwnedRepository
from lego_db.infrastructure.schema import initialize_schema
from lego_db.paths import config_path, csv_data_dir, database_path
from lego_db.presentation.gui.common import LanguageSelectionWindow
from lego_db.presentation.gui.presenter import MainPresenter
from lego_db.presentation.gui.setup_progress import SetupProgressWindow


class _App(Protocol):
    def start(self) -> None: ...
    def focus_search_entry(self, clear: bool = False) -> None: ...


def _populate_catalog_with_progress_window(root: tk.Tk, db: Database) -> None:
    """
    Shows :class:`SetupProgressWindow` only for as long as it takes to
    actually build the catalog. If the catalog already has data, this
    returns immediately without ever creating the window.
    """
    if not catalog_is_empty(db):
        return

    window = SetupProgressWindow(root)
    sets_csv = csv_data_dir() / "sets.csv"
    themes_csv = csv_data_dir() / "themes.csv"
    try:
        ensure_catalog_populated(
            db, sets_csv=sets_csv, themes_csv=themes_csv, on_progress=window.report_progress
        )
    except CatalogDataMissingError:
        window.show_error(
            "Catalog data not found.\n\n"
            "Download sets.csv and themes.csv from "
            "https://rebrickable.com/downloads/ and place them in:\n"
            f"{csv_data_dir()}"
        )
    else:
        window.show_complete()

    window.wait_for_dismissal()
    window.close()


def build_presenter(root: tk.Tk) -> MainPresenter:
    db = Database(database_path())
    initialize_schema(db)

    _populate_catalog_with_progress_window(root, db)

    catalog_repo = SQLiteCatalogRepository(db)
    owned_repo = SQLiteOwnedRepository(db)
    service = CatalogService(catalog_repo, owned_repo)
    return MainPresenter(service)


def run_gui(app_class: Callable[[tk.Tk, MainPresenter], _App]) -> None:
    root = tk.Tk()
    try:
        with suppress(Exception):
            root.attributes("-alpha", 0)

        if not config_path().exists():
            options = language_options_from_files()
            if options:
                selector = LanguageSelectionWindow(root, options)
                root.wait_window(selector.window)
            else:
                write_config("en")

        config = load_config()
        set_language(str(config.get("language", "en")))

        presenter = build_presenter(root)
        app = app_class(root, presenter)

        root.update_idletasks()
        with suppress(Exception):
            root.attributes("-alpha", 1)
        root.deiconify()
        root.lift()
        root.after_idle(root.lift)
        root.after(0, lambda: app.focus_search_entry(clear=False))

    except Exception:
        with suppress(Exception):
            root.destroy()
        raise

    app.start()
