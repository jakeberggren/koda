"""Prompt toolkit UIControl for rendering a scrollable list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType

from koda_tui.overlays.list.renderer import RowKind

if TYPE_CHECKING:
    from koda_tui.overlays.list.renderer import ListRenderer, Row
    from koda_tui.overlays.list.state import ListState


class ListControl(UIControl):
    """Scrollable list control for overlays."""

    def __init__(self, state: ListState, renderer: ListRenderer) -> None:
        self._state = state
        self._renderer = renderer
        self._scroll_offset = 0
        self._view_height = 0
        self._rows: list[Row] = []
        self._item_row_indices: list[int] = []

    def refresh(self) -> None:
        """Re-render rows from current state."""
        self._rows = self._renderer.render(self._state)
        self._item_row_indices = [i for i, row in enumerate(self._rows) if row.kind == RowKind.ITEM]

    def _ensure_scroll_bounds(self) -> None:
        """Clamp scroll offset to available rows."""
        max_offset = max(0, len(self._rows) - max(1, self._view_height))
        self._scroll_offset = max(0, min(self._scroll_offset, max_offset))

    def _selected_display_row(self) -> int | None:
        """Return the display row index of the currently selected item."""
        if not self._item_row_indices:
            return None
        selected = max(0, min(self._state.selected_index, len(self._item_row_indices) - 1))
        return self._item_row_indices[selected]

    def _group_header_index(self, row_index: int) -> int | None:
        """Return nearest group header above the given row."""
        for index in range(row_index - 1, -1, -1):
            if self._rows[index].kind == RowKind.GROUP:
                return index
        return None

    def _scroll_target_for_upward_move(self, selected_row: int) -> int:
        """Return scroll offset when selection moves above viewport."""
        group_header = self._group_header_index(selected_row)
        if group_header is not None and selected_row - group_header < self._view_height:
            return group_header
        return selected_row

    def _desired_scroll_offset(self, selected_row: int) -> int | None:
        """Return new scroll offset if selection is outside viewport."""
        if selected_row < self._scroll_offset:
            return self._scroll_target_for_upward_move(selected_row)
        if selected_row >= self._scroll_offset + self._view_height:
            return selected_row - self._view_height + 1
        # Reveal group header if needed
        group_header = self._group_header_index(selected_row)
        if (
            group_header is not None
            and group_header < self._scroll_offset
            and selected_row - group_header < self._view_height
        ):
            return group_header
        return None

    def ensure_selection_visible(self) -> None:
        """Adjust scroll so the selected item stays visible."""
        selected_row = self._selected_display_row()
        if selected_row is None:
            self._scroll_offset = 0
            self._ensure_scroll_bounds()
            return

        new_offset = self._desired_scroll_offset(selected_row)
        if new_offset is not None:
            self._scroll_offset = new_offset
        self._ensure_scroll_bounds()

    def mouse_handler(self, mouse_event: MouseEvent) -> None:
        """Handle mouse wheel scrolling."""
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self._state.move_selection(-1, wrap=False)
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self._state.move_selection(1, wrap=False)

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002
        """Create viewport content for the list."""
        self._view_height = max(1, height)
        self.refresh()
        self.ensure_selection_visible()

        visible_rows = self._rows[self._scroll_offset : self._scroll_offset + self._view_height]

        selected_row = self._selected_display_row()
        cursor_y = 0
        if selected_row is not None:
            cursor_y = max(0, min(self._view_height - 1, selected_row - self._scroll_offset))

        def get_line(i: int) -> FormattedText:
            if 0 <= i < len(visible_rows):
                return visible_rows[i].text
            return FormattedText([])

        return UIContent(
            get_line=get_line,
            line_count=len(visible_rows),
            cursor_position=Point(x=0, y=cursor_y),
        )
