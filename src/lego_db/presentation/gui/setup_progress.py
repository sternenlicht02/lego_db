"""
First-run catalog setup progress window.

Shown only when the catalog needs to be built from the bundled CSV data
(an empty database) -- normally just the very first launch. Styled like
a conventional installer: a progress bar with the file currently being
processed and a percentage, followed by an explicit completion message
the user dismisses themselves rather than the window disappearing on
its own the moment the import finishes.

This window is plain English only, by design -- it is a one-time setup
step rather than part of the app's everyday, translated UI.
"""

from __future__ import annotations

import time
import tkinter as tk
from contextlib import suppress
from tkinter import ttk
from typing import Callable, Optional

from lego_db.presentation.gui.render_throttle import RenderThrottle

_WIDTH = 420


class SetupProgressWindow:
    def __init__(self, parent: tk.Tk) -> None:
        self._parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("LEGO DB Setup")
        self.window.resizable(False, False)
        self.window.transient(parent)
        # Ignore the close button while the import is still running --
        # there is nothing sensible to do with a half-built catalog.
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)

        frame = tk.Frame(self.window, padx=24, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Setting up LEGO DB", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")

        self._status_var = tk.StringVar(value="Preparing catalog...")
        tk.Label(frame, textvariable=self._status_var, anchor="w", wraplength=_WIDTH - 48).pack(
            fill="x", pady=(12, 8)
        )

        self._bar = ttk.Progressbar(frame, orient="horizontal", length=_WIDTH - 48, mode="determinate", maximum=100)
        self._bar.pack(fill="x")

        self._detail_var = tk.StringVar(value="")
        detail_label = tk.Label(
            frame, textvariable=self._detail_var, anchor="e", font=("TkDefaultFont", 8), foreground="#666666"
        )
        detail_label.pack(fill="x", pady=(4, 0))

        self._button_row = tk.Frame(frame)
        self._ok_button: Optional[tk.Button] = None
        self._throttle = RenderThrottle()

        self._center_on_screen()
        self.window.lift()
        self.window.focus_force()
        self.window.grab_set()
        self.window.update_idletasks()

    def _center_on_screen(self) -> None:
        self.window.update_idletasks()
        width = max(self.window.winfo_reqwidth(), _WIDTH)
        height = self.window.winfo_reqheight()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def report_progress(self, label: str, current: int, total: int) -> None:
        """Matches the ``ProgressCallback`` shape used by the CSV importer."""
        is_final = total <= 0 or current >= total
        now = time.perf_counter()
        if not self._throttle.should_render(now=now, is_final=is_final):
            return
        self._throttle.mark_rendered(now)

        percent = 100 if total <= 0 else min(100, int(current * 100 / total))
        self._status_var.set(f"Importing {label}...")
        self._bar["value"] = percent
        self._detail_var.set(f"{percent}%  ({current}/{total})" if total > 0 else "100%")
        # The mainloop isn't running yet at this point in startup, so the
        # window needs a manual pump to actually redraw and stay responsive.
        # This is only reached a handful of times per phase (see
        # RenderThrottle), not once per row -- otherwise Tk's own
        # event-pump overhead would dominate a ~27,000-row import.
        with suppress(tk.TclError):
            self.window.update_idletasks()
            self.window.update()

    def show_complete(self) -> None:
        self._status_var.set("Installation complete.")
        self._bar["value"] = 100
        self._detail_var.set("")

        self._button_row.pack(fill="x", pady=(16, 0))
        self._ok_button = tk.Button(self._button_row, text="OK", padx=18, pady=4)
        self._ok_button.pack(side="right")
        self._ok_button.focus_set()

        self._center_on_screen()
        with suppress(tk.TclError):
            self.window.update_idletasks()
            self.window.update()

    def show_error(self, message: str) -> None:
        self._status_var.set(message)

        self._button_row.pack(fill="x", pady=(16, 0))
        self._ok_button = tk.Button(self._button_row, text="Close", padx=18, pady=4)
        self._ok_button.pack(side="right")
        self._ok_button.focus_set()

        self._center_on_screen()
        with suppress(tk.TclError):
            self.window.update_idletasks()
            self.window.update()

    def wait_for_dismissal(self) -> None:
        """Blocks (while still pumping events) until the OK/Close button is used."""
        dismissed = tk.BooleanVar(master=self.window, value=False)

        def _mark_dismissed() -> None:
            dismissed.set(True)

        if self._ok_button is not None:
            self._ok_button.configure(command=_mark_dismissed)
        self.window.protocol("WM_DELETE_WINDOW", _mark_dismissed)

        self.window.wait_variable(dismissed)

    def close(self) -> None:
        with suppress(Exception):
            self.window.grab_release()
        with suppress(Exception):
            self.window.destroy()
