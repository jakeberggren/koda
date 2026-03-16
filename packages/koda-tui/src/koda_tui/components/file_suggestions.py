"""File suggestions list for Koda TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import FormattedTextControl, Window
from prompt_toolkit.layout.dimension import Dimension

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda_tui.components.input_area import InputArea


class FileSuggestions:
    """Shows file suggestions above the input area."""

    MAX_LINES = 10

    def __init__(self, input_area: InputArea) -> None:
        self._input_area = input_area
        self._control = FormattedTextControl(self._get_fragments)

    def _get_fragments(self) -> StyleAndTextTuples:
        if not self._input_area.is_file_discovery_open:
            return []

        results = self._input_area.file_discovery_results[: self.MAX_LINES]
        if not results:
            return [("class:file-discovery.empty", "  no matches")]

        fragments: StyleAndTextTuples = []
        for index, path in enumerate(results):
            style = (
                "class:file-discovery.selected"
                if index == self._input_area.file_discovery_selected_index
                else "class:file-discovery.item"
            )
            if fragments:
                fragments.append(("", "\n"))
            prefix = "- " if index == self._input_area.file_discovery_selected_index else "  "
            fragments.append((style, f"{prefix}{path}"))

        return fragments

    def get_height(self) -> Dimension:
        if not self._input_area.is_file_discovery_open:
            return Dimension(min=0, max=0, preferred=0)

        count = min(len(self._input_area.file_discovery_results), self.MAX_LINES)
        preferred = count if count else 1
        return Dimension(min=0, max=self.MAX_LINES, preferred=preferred)

    def create_window(self) -> Window:
        return Window(
            content=self._control,
            height=self.get_height,
            wrap_lines=True,
            dont_extend_height=True,
            style="class:file-discovery",
        )
