"""
Main application window.

Composes :class:`TreePanel`, :class:`SelectionController`,
:class:`ContextMenuController`, :class:`DetailDialogBuilder`, and
:class:`CommandBar` into the app's layout: a search bar on top, the main
list, the related-sets list below it, and a condition-color legend
caption at the bottom. This module is composition and event wiring only
-- every rule about what a search means, what a modification does, or how
a set number normalizes lives in the domain/application layers above it.
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from lego_db.i18n.service import t
from lego_db.presentation.gui.command_bar import CommandBar
from lego_db.presentation.gui.common import (
    WINDOW_GEOMETRY,
    WINDOW_TITLE,
    center_window_on_screen,
    parse_window_geometry,
)
from lego_db.presentation.gui.context_menu import ContextMenuController
from lego_db.presentation.gui.detail_dialog import DetailDialogBuilder
from lego_db.presentation.gui.presenter import MainPresenter
from lego_db.presentation.gui.row_view import (
    MAIN_COLUMNS,
    RELATED_COLUMNS,
    format_copy_text,
    main_row_values,
    related_row_values,
)
from lego_db.presentation.gui.selection import SelectionController
from lego_db.presentation.gui.tree_panel import TreePanel

_MAIN_WIDTHS = {
    "parent_theme": 90,
    "theme": 110,
    "set_num": 80,
    "name": 232,
    "pieces": 50,
    "year": 50,
    "condition": 63,
    "note": 120,
}
_MAIN_STRETCH = {"name", "note"}
_RELATED_WIDTHS = {"set_num": 90, "name": 360, "pieces": 90, "condition": 80}
_RELATED_STRETCH = {"name"}
_OWNED_KEYWORDS = {"owned", "보유"}


def _main_headings() -> dict[str, str]:
    return {
        "parent_theme": t("parent_theme"),
        "theme": t("theme"),
        "set_num": t("set_num"),
        "name": t("name"),
        "pieces": t("pieces"),
        "year": t("release"),
        "condition": t("condition"),
        "note": t("note"),
    }


def _related_headings() -> dict[str, str]:
    return {
        "set_num": t("set_num"),
        "name": t("name"),
        "pieces": t("pieces"),
        "condition": t("condition"),
    }


class LegoDBApp:
    def __init__(self, root: tk.Tk, presenter: MainPresenter) -> None:
        self.root = root
        self.presenter = presenter

        root.title(WINDOW_TITLE)
        root.geometry(WINDOW_GEOMETRY)
        center_window_on_screen(root, *parse_window_geometry(WINDOW_GEOMETRY))

        self.detail_dialog = DetailDialogBuilder(
            root, on_copied=lambda: self.command_bar.set_status(t("copied"))
        )

        self.command_bar = CommandBar(
            root,
            root,
            on_search=self._search,
            on_modify=self._modify,
            on_detail=self._show_detail,
            on_copy=self._copy_clipboard,
            is_modal_open=lambda: self.detail_dialog.is_open,
        )

        main_frame = tk.LabelFrame(root, text=t("main_info"))
        main_frame.pack(fill="both", expand=True, padx=10, pady=6)
        self.main_panel = TreePanel(
            main_frame,
            columns=MAIN_COLUMNS,
            headings=_main_headings(),
            widths=_MAIN_WIDTHS,
            stretch=_MAIN_STRETCH,
            height=12,
            row_values=main_row_values,
        )

        related_frame = tk.LabelFrame(root, text=t("sub_info"))
        related_frame.pack(fill="both", expand=True, padx=10, pady=6)
        self.related_panel = TreePanel(
            related_frame,
            columns=RELATED_COLUMNS,
            headings=_related_headings(),
            widths=_RELATED_WIDTHS,
            stretch=_RELATED_STRETCH,
            height=8,
            row_values=related_row_values,
        )

        tk.Label(root, text=t("condition_desc"), font=("TkDefaultFont", 8)).pack(pady=(0, 6))

        self.selection = SelectionController([self.main_panel, self.related_panel])
        self.main_panel.bind_select(self._on_main_select)
        self.related_panel.bind_select(self._on_related_select)
        self.main_panel.bind_double_click(lambda _e: self._show_detail())
        self.related_panel.bind_double_click(lambda _e: self._show_detail())

        self.context_menu = ContextMenuController(
            root, self.selection, is_owned=self.presenter.is_owned, on_toggle=self._toggle_owned
        )
        self.context_menu.attach(self.main_panel)
        self.context_menu.attach(self.related_panel)

        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start(self) -> None:
        self.root.mainloop()

    def on_close(self) -> None:
        self.detail_dialog.close()
        self.root.destroy()

    def focus_search_entry(self, clear: bool = False) -> None:
        self.command_bar.focus_search_entry(clear=clear)

    def _clear_all(self) -> None:
        self.main_panel.clear()
        self.related_panel.clear()

    def _render_search_results(self, text: str) -> int:
        self._clear_all()
        rows = self.presenter.search(text)
        return self.main_panel.populate(rows)

    def _search(self, text: str) -> None:
        count = self._render_search_results(text)
        self.command_bar.set_status(f"{count}{t('result_count')}", delay=0)

    def _on_main_select(self, _event=None) -> None:
        self.selection.mark_active(self.main_panel)
        set_num = self.main_panel.selected_set_num()
        if not set_num:
            self.related_panel.clear()
            return
        self._update_related(set_num)

    def _on_related_select(self, _event=None) -> None:
        self.selection.mark_active(self.related_panel)

    def _update_related(self, set_num: str) -> None:
        self.related_panel.clear()
        rows = self.presenter.related(set_num)
        self.related_panel.populate(rows)

    def _get_selected_set(self) -> Optional[str]:
        return self.selection.current_set_num()

    def _show_detail(self) -> None:
        set_num = self._get_selected_set()
        if not set_num:
            self.command_bar.set_status(t("no_selection"))
            return
        row = self.presenter.detail(set_num)
        if row is None:
            self.command_bar.set_status(t("no_data"))
            return
        self.detail_dialog.show(row)

    def _copy_clipboard(self) -> None:
        set_num = self._get_selected_set()
        if not set_num:
            self.command_bar.set_status(t("no_selection"))
            return
        row = self.presenter.detail(set_num)
        if row is None:
            self.command_bar.set_status(t("no_data"))
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(format_copy_text(row, normalize=True))
        self.command_bar.set_status(t("copied"))

    def _toggle_owned(self, set_num: str) -> None:
        self.presenter.toggle_owned(set_num)
        self.command_bar.set_status(t("modify_done"))
        self._refresh_after_owned_change(set_num)

    def _refresh_after_owned_change(self, set_num: str) -> None:
        # Matches the live search box text, not necessarily the last
        # *executed* search -- see the design notes on this refresh path.
        text = self.command_bar.search_var.get().strip()

        if not text:
            self._search("")
            return

        head = text.split(maxsplit=1)[0].casefold()
        if head in _OWNED_KEYWORDS:
            self._search(text)
            return

        row = self.presenter.detail(set_num)
        if row is None:
            return
        self.main_panel.update_row(set_num, row)
        self.related_panel.update_row(set_num, row)

    def _modify(self, text: str) -> None:
        result = self.presenter.apply_modification(text)

        if result.error is not None:
            self.command_bar.set_status(f"{t('modify_fail')}: {result.error}")
        elif result.changed and result.partial:
            self.command_bar.set_status(t("modify_partial"))
        elif result.changed:
            self.command_bar.set_status(t("modify_done"))
        else:
            self.command_bar.set_status(t("modify_fail"))

        self.command_bar.clear_entry_and_refocus()
        self._render_search_results(self.presenter.last_search_text)


def main() -> None:
    from lego_db.presentation.gui.bootstrap import run_gui

    run_gui(LegoDBApp)


if __name__ == "__main__":
    main()
