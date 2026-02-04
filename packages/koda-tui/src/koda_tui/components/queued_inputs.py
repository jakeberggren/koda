"""Queued inputs overlay for Koda TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import FormattedTextControl, Window
from prompt_toolkit.layout.dimension import Dimension

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda_tui.state import AppState


class QueuedInputs:
    """Shows queued user inputs above the input area."""

    MAX_LINES = 3

    def __init__(self, state: AppState) -> None:
        self._state = state
        self._control = FormattedTextControl(self._get_fragments)

    def _get_fragments(self) -> StyleAndTextTuples:
        if not self._state.pending_inputs:
            return []
        n = len(self._state.pending_inputs)
        s = "s" if n != 1 else ""
        fragments: StyleAndTextTuples = [
            (
                "class:queued-inputs.title",
                f"  {n} message{s} queued (esc to clear)",
            ),
        ]
        for item in self._state.pending_inputs[-self.MAX_LINES :]:
            fragments.append(("", "\n"))
            fragments.append(("", f"  {item}"))
        return fragments

    def get_height(self) -> Dimension:
        count = min(len(self._state.pending_inputs), self.MAX_LINES)
        # +1 for the title line
        preferred = count + 1 if count else 0
        return Dimension(min=0, max=self.MAX_LINES + 1, preferred=preferred)

    def create_window(self) -> Window:
        return Window(
            content=self._control,
            height=self.get_height,
            wrap_lines=True,
            dont_extend_height=True,
            style="class:queued-inputs",
        )
