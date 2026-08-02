"""
Detail dialog builder.

Builds the modal "set detail" Toplevel window: field labels, a
normalize-on-copy checkbox, and copy/close buttons.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from lego_db.application.catalog_row import CatalogRow
from lego_db.i18n.service import t
from lego_db.presentation.gui.common import DETAIL_HEIGHT, DETAIL_WIDTH, center_over_parent
from lego_db.presentation.gui.row_view import format_copy_text


class DetailDialogBuilder:
    def __init__(self, root: tk.Tk, *, on_copied: Callable[[], None]) -> None:
        self._root = root
        self._on_copied = on_copied
        self._window: Optional[tk.Toplevel] = None

    @property
    def is_open(self) -> bool:
        return self._window is not None and self._window.winfo_exists()

    def close(self) -> None:
        try:
            if self._window is not None and self._window.winfo_exists():
                self._window.destroy()
        finally:
            self._window = None

    def show(self, row: CatalogRow) -> None:
        win = tk.Toplevel(self._root)
        self._window = win
        win.withdraw()

        win.title(t("detail"))
        win.transient(self._root)
        win.protocol("WM_DELETE_WINDOW", self.close)

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True)
        content = tk.Frame(frame, padx=16, pady=10)
        content.pack(fill="both", expand=True)

        fields = (
            ("set_num", row.set_num),
            ("parent_theme", row.parent_theme),
            ("theme", row.theme),
            ("name", row.name),
            ("pieces", row.num_parts if row.num_parts is not None else ""),
            ("release", row.year if row.year is not None else ""),
            ("condition", str(row.condition) if row.condition is not None else "-"),
            ("note", row.note or "-"),
        )
        for key, value in fields:
            tk.Label(content, text=f"{t(key)}: {value}", anchor="w", justify="left").pack(fill="x", pady=2)

        normalize_var = tk.BooleanVar(value=True)
        tk.Checkbutton(content, text=t("normalize"), variable=normalize_var).pack(pady=(6, 0))

        def copy() -> None:
            text = format_copy_text(row, normalize=normalize_var.get())
            self._root.clipboard_clear()
            self._root.clipboard_append(text)
            self._on_copied()

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill="x", pady=10)
        center_frame = tk.Frame(btn_frame)
        center_frame.pack(anchor="center")

        tk.Button(center_frame, text=t("copy"), command=copy, padx=10, pady=6).pack(side="left", padx=(0, 6))
        tk.Button(center_frame, text=t("close"), command=self.close, padx=10, pady=6).pack(side="left")

        win.update_idletasks()
        center_over_parent(self._root, win, DETAIL_WIDTH, DETAIL_HEIGHT)
        win.deiconify()
        win.lift()
        win.focus_force()
        win.grab_set()
