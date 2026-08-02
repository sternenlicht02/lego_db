"""
Tree renderer.

Builds one ``Treeview`` (with scrollbars and condition-based row coloring)
and knows how to populate it from :class:`CatalogRow` data. The main list
and the related-sets list are both instances of this same class,
parametrized by which columns they show -- there is nothing "main" or
"related" specific about tree construction itself.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, Optional

from lego_db.application.catalog_row import CatalogRow
from lego_db.presentation.gui.row_view import CONDITION_TAG_COLORS, condition_tag


class TreePanel:
    def __init__(
        self,
        parent: tk.Widget,
        *,
        columns: tuple[str, ...],
        headings: dict[str, str],
        widths: dict[str, int],
        stretch: set[str],
        height: int,
        row_values: Callable[[CatalogRow], tuple],
    ) -> None:
        self._row_values = row_values
        self._set_num_index = columns.index("set_num")

        container = tk.Frame(parent)
        container.pack(fill="both", expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=height)
        vsb = tk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        hsb = tk.Scrollbar(container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, anchor="center", width=widths[col], stretch=(col in stretch))

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        for tag, color in CONDITION_TAG_COLORS.items():
            self.tree.tag_configure(tag, background=color)

    def clear(self) -> None:
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)
        self.tree.selection_remove(self.tree.selection())
        self.tree.yview_moveto(0)

    def populate(self, rows: Iterable[CatalogRow]) -> int:
        count = 0
        for row in rows:
            self.tree.insert("", "end", values=self._row_values(row), tags=(condition_tag(row),))
            count += 1
        return count

    def update_row(self, set_num: str, row: CatalogRow) -> bool:
        """Update an already-inserted row in place, preserving scroll/selection."""
        updated = False
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if not values:
                continue
            if str(values[self._set_num_index]) == set_num:
                self.tree.item(item, values=self._row_values(row), tags=(condition_tag(row),))
                updated = True
        return updated

    def selected_set_num(self) -> Optional[str]:
        selection = self.tree.selection()
        if not selection:
            return None
        values = self.tree.item(selection[0]).get("values", [])
        if not values:
            return None
        return str(values[self._set_num_index])

    def set_num_at(self, item_id: str) -> Optional[str]:
        values = self.tree.item(item_id).get("values", [])
        if not values:
            return None
        return str(values[self._set_num_index])

    def bind_select(self, callback) -> None:
        self.tree.bind("<<TreeviewSelect>>", callback)

    def bind_double_click(self, callback) -> None:
        self.tree.bind("<Double-1>", callback)

    def bind_right_click(self, callback) -> None:
        self.tree.bind("<Button-3>", callback)
