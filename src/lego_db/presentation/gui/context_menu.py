"""
Right-click context menu controller.

On right-click over a tree row: selects that row, marks it as the active
selection, and shows a one-item popup menu to add/remove it from owned --
the only context-menu action the app has.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from lego_db.i18n.service import t
from lego_db.presentation.gui.selection import SelectionController
from lego_db.presentation.gui.tree_panel import TreePanel


class ContextMenuController:
    def __init__(
        self,
        root: tk.Tk,
        selection: SelectionController,
        *,
        is_owned: Callable[[str], bool],
        on_toggle: Callable[[str], None],
    ) -> None:
        self._root = root
        self._selection = selection
        self._is_owned = is_owned
        self._on_toggle = on_toggle

    def attach(self, panel: TreePanel) -> None:
        panel.bind_right_click(lambda event: self._show(event, panel))

    def _show(self, event: tk.Event, panel: TreePanel) -> str:
        item_id = panel.tree.identify_row(event.y)
        if not item_id:
            return "break"

        panel.tree.selection_set(item_id)
        panel.tree.focus(item_id)
        self._selection.mark_active(panel)

        set_num = panel.set_num_at(item_id)
        if not set_num:
            return "break"

        owned = self._is_owned(set_num)
        menu = tk.Menu(self._root, tearoff=0)
        menu.add_command(
            label=t("remove_owned") if owned else t("add_owned"),
            command=lambda: self._on_toggle(set_num),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"
