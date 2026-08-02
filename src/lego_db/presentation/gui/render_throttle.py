"""
A simple time-based throttle for expensive per-row UI refreshes.

:class:`SetupProgressWindow` reports progress once per CSV row (tens of
thousands of calls for the full dataset); actually redrawing the window
on every single one of those would make Tk's event-pump overhead dominate
the whole import, turning a sub-second job into a multi-second one for no
visible benefit. This decides which calls are worth an actual redraw.

Kept free of any ``tkinter`` import so the decision itself -- not the
widget code around it -- can be unit-tested without a display.
"""

from __future__ import annotations

from typing import Optional


class RenderThrottle:
    def __init__(self, min_interval_seconds: float = 0.05) -> None:
        self._min_interval = min_interval_seconds
        self._last_render_time: Optional[float] = None

    def should_render(self, *, now: float, is_final: bool) -> bool:
        """
        True if enough time has passed since the last render to bother
        with another one. Always true for the very first call and for
        whatever call marks a phase as finished, so the window never
        opens on stale numbers and always ends up showing 100%.
        """
        if is_final:
            return True
        if self._last_render_time is None:
            return True
        return (now - self._last_render_time) >= self._min_interval

    def mark_rendered(self, now: float) -> None:
        self._last_render_time = now
