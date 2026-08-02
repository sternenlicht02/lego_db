"""
Selection controller.

Tracks which of several :class:`TreePanel` instances most recently had a
selection made in it, and resolves "the currently selected set number"
across all of them. Selecting a row in either the main list or the
related list makes that row the target for Detail/Copy/right-click,
regardless of which list it came from -- this is the one place that
decides which panel wins when more than one has a selection.
"""

from __future__ import annotations

from typing import Optional

from lego_db.presentation.gui.tree_panel import TreePanel


class SelectionController:
    def __init__(self, panels: list[TreePanel]) -> None:
        self._panels = panels
        self._last_active: Optional[TreePanel] = None

    def mark_active(self, panel: TreePanel) -> None:
        self._last_active = panel

    def current_set_num(self) -> Optional[str]:
        ordered: list[TreePanel] = []
        if self._last_active is not None:
            ordered.append(self._last_active)
        for panel in self._panels:
            if panel not in ordered:
                ordered.append(panel)

        for panel in ordered:
            set_num = panel.selected_set_num()
            if set_num is not None:
                return set_num
        return None
