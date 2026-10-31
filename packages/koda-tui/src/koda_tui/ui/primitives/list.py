"""List primitive: a scrollable, searchable list with one selected item."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, override

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import UIContent, UIControl, Window
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType

from koda_tui.appearance import Tokens, compose
from koda_tui.ui.primitives.text import ELLIPSIS

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.layout.containers import GetLinePrefixCallable
    from prompt_toolkit.layout.dimension import AnyDimension

SELECTED_STYLE = compose(Tokens.Surface.SELECTED, Tokens.Text.STRONG)
CURRENT_STYLE = compose(Tokens.Text.ACCENT, Tokens.Text.STRONG)
GROUP_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.STRONG)
EMPTY_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)


@dataclass(frozen=True, slots=True, kw_only=True)
class ListItem[T]:
    """A selectable item in a list, carrying ``data`` for whoever acts on it."""

    label: str
    data: T
    detail: str = ""
    group: str | None = None
    marker: str | None = None  # Shown before the label, e.g. "✓".
    current: bool = False  # Marks the active choice, e.g. the selected model.


class RowKind(Enum):
    """Kind of row in the rendered list."""

    ITEM = auto()
    GROUP = auto()
    EMPTY = auto()
    SPACER = auto()
    HEADING = auto()


@dataclass(frozen=True, slots=True)
class Row:
    """A rendered row ready for display."""

    kind: RowKind
    text: FormattedText
    item: ListItem[Any] | None = None


class ListState[T]:
    """The items of a list, filtered by search text, with one item selected.

    Items with a ``group`` are grouped under it; ungrouped items come first.
    """

    def __init__(self, items: list[ListItem[T]]) -> None:
        self.items = items
        self.search_text = ""
        self.selected_index = 0
        self._filtered_items = list(items)

    def set_search(self, text: str) -> None:
        """Filter items by search text and reset selection."""
        self.search_text = text.lower()
        self._filtered_items = [
            item for item in self.items if self.search_text in item.label.lower()
        ]
        self.selected_index = 0

    def set_items(self, items: list[ListItem[T]]) -> None:
        """Replace the items, keeping the selected item selected if it is still there."""
        selected = self.selected_item
        self.items = items
        self.set_search(self.search_text)
        if selected in self.display_items:
            self.selected_index = self.display_items.index(selected)

    @property
    def filtered_items(self) -> list[ListItem[T]]:
        return self._filtered_items

    @property
    def selected_item(self) -> ListItem[T] | None:
        """Return the selected item in visual display order."""
        display_items = self.display_items
        if not display_items:
            return None
        return display_items[max(0, min(self.selected_index, len(display_items) - 1))]

    @property
    def display_items(self) -> list[ListItem[T]]:
        """Return filtered items in the same order rendered on screen."""
        return [item for _group, items in self.grouped_items() for item in items]

    def move_selection(self, delta: int, *, wrap: bool = False) -> None:
        """Move selection by delta. If wrap is True, wrap around at boundaries."""
        if not self._filtered_items:
            self.selected_index = 0
            return
        count = len(self._filtered_items)
        if wrap:
            self.selected_index = (self.selected_index + delta) % count
        else:
            self.selected_index = max(0, min(self.selected_index + delta, count - 1))

    def grouped_items(self) -> list[tuple[str | None, list[ListItem[T]]]]:
        """Return items grouped by their group label."""
        grouped: list[tuple[str | None, list[ListItem[T]]]] = []
        group_map: dict[str, list[ListItem[T]]] = {}
        ungrouped: list[ListItem[T]] = []

        for item in self._filtered_items:
            if not item.group:
                ungrouped.append(item)
                continue
            if item.group not in group_map:
                group_map[item.group] = []
                grouped.append((item.group, group_map[item.group]))
            group_map[item.group].append(item)

        if ungrouped:
            return [(None, ungrouped), *grouped]
        return grouped


class List:
    """Shows a ListState: group headers, the selected item, scrolled to stay visible."""

    def __init__(
        self,
        state: ListState[Any],
        *,
        heading: str | None = None,
        empty_message: str = "No results found",
        height: AnyDimension = None,
        label_width: int | None = None,
    ) -> None:
        self.state = state
        self._heading = heading
        self._empty_message = empty_message
        self._label_width = label_width  # Longer labels are cut to it.
        self._window = Window(ListControl(self), height=height, dont_extend_height=True)

    def __pt_container__(self) -> Window:
        return self._window

    def rows(self) -> list[Row]:
        """Render all rows from the current state."""
        rows: list[Row] = []
        if self._heading:
            rows.append(Row(RowKind.HEADING, FormattedText([(GROUP_STYLE, self._heading)])))

        if not self.state.filtered_items:
            empty = FormattedText([(EMPTY_STYLE, f"  {self._empty_message}")])
            return [*rows, Row(RowKind.EMPTY, empty)]
        return rows + self._item_rows(spacer_first=bool(rows))

    def _label_column(self) -> int:
        """The width labels are padded to: the longest, up to ``label_width``."""
        width = max(len(item.label) for item in self.state.filtered_items)
        return width if self._label_width is None else min(width, self._label_width)

    def _item_rows(self, *, spacer_first: bool) -> list[Row]:
        """Rows for the filtered items, each group under its header."""
        rows: list[Row] = []
        width = self._label_column()
        index = 0
        for group, items in self.state.grouped_items():
            if group:
                if rows or spacer_first:
                    rows.append(Row(RowKind.SPACER, FormattedText([])))
                rows.append(Row(RowKind.GROUP, FormattedText([(GROUP_STYLE, group)])))
            for item in items:
                selected = index == self.state.selected_index
                rows.append(_item_row(item, selected=selected, width=width))
                index += 1
        return rows


def _item_row(item: ListItem[Any], *, selected: bool, width: int) -> Row:
    """A row for one item: marker or selection indicator, padded label, then detail."""
    style = SELECTED_STYLE if selected else Tokens.Text.DEFAULT
    label_style = CURRENT_STYLE if item.current and not selected else style
    marker = "*" if item.current else item.marker

    line: StyleAndTextTuples = []
    if marker is not None:
        line.append((style if selected else CURRENT_STYLE, f"{marker} "))
    else:
        line.append((style, "- " if selected else "  "))
    line.append((label_style, _cut(item.label, width).ljust(width)))
    if item.detail:
        line.append((SELECTED_STYLE if selected else Tokens.Text.MUTED, f"  {item.detail}"))
    return Row(RowKind.ITEM, FormattedText(line), item)


def _cut(label: str, width: int) -> str:
    """``label`` cut to ``width``, ending in an ellipsis when cut."""
    if len(label) <= width:
        return label
    if width <= len(ELLIPSIS):
        return ELLIPSIS[:width]
    return label[: width - len(ELLIPSIS)] + ELLIPSIS


class ListControl(UIControl):
    """Draws a List's rows, scrolled so the selected item stays visible."""

    def __init__(self, items: List) -> None:
        self._list = items
        self._scroll_offset = 0
        self._view_height = 0
        self._rows: list[Row] = []
        self._item_row_indices: list[int] = []

    @override
    def preferred_height(
        self,
        width: int,
        max_available_height: int,
        wrap_lines: bool,
        get_line_prefix: GetLinePrefixCallable | None,
    ) -> int:
        return len(self._list.rows())

    def _refresh(self) -> None:
        self._rows = self._list.rows()
        self._item_row_indices = [i for i, row in enumerate(self._rows) if row.kind == RowKind.ITEM]

    def _ensure_scroll_bounds(self) -> None:
        """Clamp scroll offset to available rows."""
        max_offset = max(0, len(self._rows) - max(1, self._view_height))
        self._scroll_offset = max(0, min(self._scroll_offset, max_offset))

    def _selected_display_row(self) -> int | None:
        """Return the display row index of the currently selected item."""
        if not self._item_row_indices:
            return None
        selected = max(0, min(self._list.state.selected_index, len(self._item_row_indices) - 1))
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

    def _ensure_selection_visible(self) -> None:
        """Adjust scroll so the selected item stays visible."""
        selected_row = self._selected_display_row()
        if selected_row is None:
            self._scroll_offset = 0
        elif (new_offset := self._desired_scroll_offset(selected_row)) is not None:
            self._scroll_offset = new_offset
        self._ensure_scroll_bounds()

    def mouse_handler(self, mouse_event: MouseEvent) -> None:
        """Handle mouse wheel scrolling."""
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self._list.state.move_selection(-1, wrap=False)
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self._list.state.move_selection(1, wrap=False)

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002
        """Create viewport content for the list."""
        self._view_height = max(1, height)
        self._refresh()
        self._ensure_selection_visible()

        visible_rows = self._rows[self._scroll_offset : self._scroll_offset + self._view_height]
        selected_row = self._selected_display_row()
        cursor_y = 0
        if selected_row is not None:
            cursor_y = max(0, min(self._view_height - 1, selected_row - self._scroll_offset))

        def get_line(i: int) -> FormattedText:
            return visible_rows[i].text if 0 <= i < len(visible_rows) else FormattedText([])

        return UIContent(
            get_line=get_line,
            line_count=len(visible_rows),
            cursor_position=Point(x=0, y=cursor_y),
        )
