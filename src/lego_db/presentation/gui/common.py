"""
Shared constants and small reusable widgets.

The application module (``app.py``) uses these instead of defining its
own copy of the same window-centering math, hover tooltip, or first-run
language picker.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from lego_db.i18n.service import write_config

WINDOW_TITLE = "LEGO DB"
WINDOW_GEOMETRY = "920x640"
DETAIL_WIDTH = 440
DETAIL_HEIGHT = 300


def parse_window_geometry(geometry: str) -> tuple[int, int]:
    size_part = geometry.split("+", 1)[0]
    width_str, height_str = size_part.split("x", 1)
    return int(width_str), int(height_str)


def center_window_on_screen(window: tk.Misc, width: int, height: int) -> None:
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def center_over_parent(parent: tk.Tk, child: tk.Toplevel, width: int, height: int) -> None:
    parent.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
    child.geometry(f"{width}x{height}+{x}+{y}")


class HoverTooltip:
    """A small yellow tooltip shown while the mouse hovers over a widget."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None) -> None:
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{x}+{y}")
        tk.Label(
            self.tip,
            text=self.text,
            background="#FFFBEA",
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=3,
        ).pack()

    def hide(self, _event=None) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class LanguageSelectionWindow:
    """
    First-run language selection dialog.

    Shown only when ``config.json`` doesn't exist yet. Confirming saves the
    chosen language; closing the window any other way (Escape, the window's
    close button) saves "en" as a safe default rather than whatever was
    left selected in the combo box.
    """

    def __init__(self, parent: tk.Tk, options: list[tuple[str, str]]) -> None:
        self.parent = parent
        self.options = options
        self.codes = [code for code, _ in options]
        self.label_to_code = {label: code for code, label in options}

        self.window = tk.Toplevel(parent)
        self.window.title(WINDOW_TITLE)
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self._close_default)
        self.window.bind("<Escape>", self._on_escape)

        self.selected = tk.StringVar()
        display_values = [label for _, label in options]

        frame = tk.Frame(self.window, padx=16, pady=14)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Select a language", anchor="w").pack(fill="x", pady=(0, 8))

        self.combo = ttk.Combobox(
            frame,
            textvariable=self.selected,
            values=display_values,
            state="readonly",
            width=42,
        )
        self.combo.pack(fill="x")

        default_display = self._display_for_code("en")
        if default_display is None and display_values:
            default_display = display_values[0]
        if default_display is not None:
            self.combo.set(default_display)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill="x", pady=(16, 0))
        tk.Button(btn_frame, text="confirm", command=self._confirm).pack(side="right")

        self.window.update_idletasks()
        w = max(self.window.winfo_reqwidth(), 360)
        h = max(self.window.winfo_reqheight(), 200)
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        x = max(0, (screen_w - w) // 2)
        y = max(0, (screen_h - h) // 2)
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.lift()
        self.window.focus_force()
        self.window.grab_set()

    def _display_for_code(self, code: str) -> Optional[str]:
        for candidate_code, label in self.options:
            if candidate_code == code:
                return label
        return None

    def _save(self, code: str) -> None:
        if code not in self.codes and self.codes:
            code = "en" if "en" in self.codes else self.codes[0]
        write_config(code)

    def _confirm(self) -> None:
        label = self.combo.get().strip()
        code = self.label_to_code.get(label, "en")
        self._save(code)
        self.window.destroy()

    def _close_default(self) -> None:
        self._save("en")
        self.window.destroy()

    def _on_escape(self, _event=None) -> str:
        self._close_default()
        return "break"
