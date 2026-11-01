"""List widget: items to choose from, searchable and grouped, with one selected."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from prompt_toolkit.utils import get_cwidth

from koda_tui.appearance import Tokens, compose
from koda_tui.ui.fragments import truncate_text
from koda_tui.ui.primitives import Lines, Rows

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples
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


class List[T]:
    """Shows a ListState: an optional heading, then each group under its header, a blank
    line apart. Each item shows its marker, its label in a column, then its detail; the
    selected one is highlighted and kept in view with its group's header.

    The mouse wheel moves the selection. ``label_width`` cuts longer labels.
    """

    def __init__(
        self,
        state: ListState[T],
        *,
        heading: str | None = None,
        empty_message: str = "No results found",
        height: AnyDimension = None,
        label_width: int | None = None,
    ) -> None:
        self.state = state
        self._heading = heading
        self._empty_message = empty_message
        self._label_width = label_width
        self._rows = Rows(self.lines, on_scroll=state.move_selection, height=height)

    def __pt_container__(self) -> Rows:
        return self._rows

    def lines(self) -> Lines:
        """The lines for the state as it is now, with the selected item's marked."""
        heading: list[StyleAndTextTuples] = (
            [[(GROUP_STYLE, self._heading)]] if self._heading else []
        )
        if not self.state.filtered_items:
            return Lines([*heading, [(EMPTY_STYLE, f"  {self._empty_message}")]])
        return self._item_lines(heading)

    def _item_lines(self, lines: list[StyleAndTextTuples]) -> Lines:
        """``lines``, then the filtered items, each group under its header."""
        chosen = min(self.state.selected_index, len(self.state.filtered_items) - 1)
        width = self._label_column()
        selected = anchor = header = None
        index = 0
        for group, items in self.state.grouped_items():
            if group:
                lines += _group_header(group, spaced=bool(lines))
                header = len(lines) - 1
            for item in items:
                if index == chosen:
                    selected, anchor = len(lines), header
                lines.append(_item_line(item, selected=index == chosen, width=width))
                index += 1
        return Lines(lines, selected=selected, anchor=anchor)

    def _label_column(self) -> int:
        """The width labels are padded to, in cells: the longest, up to ``label_width``."""
        width = max(get_cwidth(item.label) for item in self.state.filtered_items)
        return width if self._label_width is None else min(width, self._label_width)


def _group_header(group: str, *, spaced: bool) -> list[StyleAndTextTuples]:
    """A group's header, after a blank line if ``spaced``."""
    header: StyleAndTextTuples = [(GROUP_STYLE, group)]
    return [[], header] if spaced else [header]


def _item_line[T](item: ListItem[T], *, selected: bool, width: int) -> StyleAndTextTuples:
    """One item: its marker or the selection indicator, its padded label, then detail."""
    style = SELECTED_STYLE if selected else Tokens.Text.DEFAULT
    label_style = CURRENT_STYLE if item.current and not selected else style
    marker = "*" if item.current else item.marker

    line: StyleAndTextTuples = []
    if marker is not None:
        line.append((style if selected else CURRENT_STYLE, f"{marker} "))
    else:
        line.append((style, "- " if selected else "  "))
    label = truncate_text(item.label, width)
    line.append((label_style, label + " " * (width - get_cwidth(label))))
    if item.detail:
        line.append((SELECTED_STYLE if selected else Tokens.Text.MUTED, f"  {item.detail}"))
    return line
