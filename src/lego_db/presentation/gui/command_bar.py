"""
Command dispatcher.

Owns the search entry's key bindings (Enter to search, arrow/home/end for
cursor movement, the global "/" focus shortcut), the four action buttons,
and the status message with its auto-clear timer. Each button just calls
an injected callback -- this module knows nothing about the presenter,
the tree panels, or the detail dialog, only how to dispatch to them.
"""

from __future__ import annotations

import tkinter as tk
from contextlib import suppress
from tkinter import ttk
from typing import Callable, Optional

from lego_db.i18n.service import t
from lego_db.presentation.gui.common import HoverTooltip


class CommandBar:
    def __init__(
        self,
        root: tk.Tk,
        parent: tk.Widget,
        *,
        on_search: Callable[[str], None],
        on_modify: Callable[[str], None],
        on_detail: Callable[[], None],
        on_copy: Callable[[], None],
        is_modal_open: Callable[[], bool],
    ) -> None:
        self._root = root
        self._on_search = on_search
        self._on_modify = on_modify
        self._is_modal_open = is_modal_open
        self._status_after_id: Optional[str] = None

        top = tk.Frame(parent)
        top.pack(fill="x", padx=10, pady=6)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(top, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda _e: self._dispatch_search())
        self.search_entry.bind("<Up>", self._move_cursor_start)
        self.search_entry.bind("<Down>", self._move_cursor_end)
        self.search_entry.bind("<Home>", self._move_cursor_start)
        self.search_entry.bind("<End>", self._move_cursor_end)

        root.bind_all("<KeyPress>", self._on_global_keypress, add="+")

        tk.Button(top, text=t("search"), command=self._dispatch_search).pack(side="left", padx=4)
        tk.Button(top, text=t("modify"), command=self._dispatch_modify).pack(side="left", padx=4)
        tk.Button(top, text=t("detail"), command=on_detail).pack(side="left", padx=4)
        tk.Button(top, text=t("copy"), command=on_copy).pack(side="left", padx=4)

        bottom = tk.Frame(parent)
        bottom.pack(fill="x", padx=10, pady=(0, 8))

        self.status = tk.StringVar(value="")
        tk.Label(bottom, textvariable=self.status, anchor="w").pack(side="left", fill="x", expand=True)
        help_label = tk.Label(bottom, text="?", relief="groove", width=2)
        help_label.pack(side="right")
        HoverTooltip(help_label, "+0000-1\n-0000-1\n2>0000-1\n[{}]>0000-1".format(t("note")))

    def _dispatch_search(self) -> None:
        self._on_search(self.search_var.get().strip())

    def _dispatch_modify(self) -> None:
        self._on_modify(self.search_var.get())

    def set_status(self, text: str, delay: Optional[int] = 5000) -> None:
        self.status.set(text)
        if self._status_after_id is not None:
            with suppress(tk.TclError):
                self._root.after_cancel(self._status_after_id)
            self._status_after_id = None
        if delay and delay > 0:
            self._status_after_id = self._root.after(delay, self._clear_status_if_active)

    def _clear_status_if_active(self) -> None:
        self.status.set("")
        self._status_after_id = None

    def clear_entry_and_refocus(self) -> None:
        self.search_var.set("")
        self.search_entry.focus()

    def focus_search_entry(self, *, clear: bool = False) -> None:
        if self.search_entry.winfo_exists():
            self.search_entry.focus_force()
            if clear:
                self.search_entry.delete(0, tk.END)
            self.search_entry.icursor(0)

    def _move_cursor_start(self, _event=None) -> str:
        self.search_entry.icursor(0)
        return "break"

    def _move_cursor_end(self, _event=None) -> str:
        self.search_entry.icursor(tk.END)
        return "break"

    def _on_global_keypress(self, event: tk.Event) -> Optional[str]:
        if event.char != "/" and event.keysym.lower() != "slash":
            return None
        if self._is_modal_open():
            return None
        if event.widget is self.search_entry:
            return None
        if isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Text)):
            return None
        self.focus_search_entry(clear=True)
        return "break"
