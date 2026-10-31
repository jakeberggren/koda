"""Pure list row rendering from state to display rows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import FormattedText

from koda_tui.appearance import Tokens, compose

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda_tui.overlays.list.state import ListState
    from koda_tui.palette.items import ListItem


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
    item: ListItem | None = None


SELECTED_STYLE = compose(Tokens.Surface.SELECTED, Tokens.Text.STRONG)
# Marks the item that is currently active, e.g. the selected model.
CURRENT_STYLE = compose(Tokens.Text.ACCENT, Tokens.Text.STRONG)
_GROUP_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.STRONG)
_EMPTY_STYLE = compose(Tokens.Text.MUTED, Tokens.Text.EMPHASIS)


@dataclass(frozen=True, slots=True)
class RenderOptions:
    """Options that affect how rows are rendered."""

    list_heading: str | None = None
    empty_message: str = "No results found"
    selected_style: str = SELECTED_STYLE
    item_style: str = Tokens.Text.DEFAULT
    dim_style: str = Tokens.Text.MUTED
    marker_style: str = CURRENT_STYLE
    group_style: str = _GROUP_STYLE


class ListRenderer:
    """Render ListState into display Rows."""

    def __init__(self, options: RenderOptions | None = None) -> None:
        self._options = options or RenderOptions()

    @staticmethod
    def _max_label_width(items: list[ListItem]) -> int:
        return max((len(item.label) for item in items), default=0)

    def _item_row(self, item: ListItem, *, is_selected: bool, max_label_width: int) -> Row:
        """Build a formatted row for a single item."""
        style = self._options.selected_style if is_selected else self._options.item_style
        dim_style = self._options.selected_style if is_selected else self._options.dim_style
        marker_style = self._options.marker_style

        # Determine label style (marker override or default)
        label_style = style
        if item.marker and item.marker_style and not is_selected:
            label_style = item.marker_style

        padded_label = item.label.ljust(max_label_width)
        line: StyleAndTextTuples = []

        # Marker / selection indicator
        if item.marker is not None:
            render_marker_style = style if is_selected else marker_style
            line.append((render_marker_style, f"{item.marker} "))
        elif is_selected:
            line.append((style, "- "))
        else:
            line.append((style, "  "))

        line.append((label_style, padded_label))

        if item.detail:
            line.append((dim_style, f"  {item.detail}"))

        return Row(kind=RowKind.ITEM, text=FormattedText(line), item=item)

    @staticmethod
    def _spacer_row() -> Row:
        return Row(kind=RowKind.SPACER, text=FormattedText([]))

    @staticmethod
    def _group_row(group: str, style: str) -> Row:
        return Row(kind=RowKind.GROUP, text=FormattedText([(style, group)]))

    @staticmethod
    def _heading_row(text: str) -> Row:
        return Row(
            kind=RowKind.HEADING,
            text=FormattedText([(_GROUP_STYLE, text)]),
        )

    @staticmethod
    def _empty_row(message: str) -> Row:
        return Row(
            kind=RowKind.EMPTY,
            text=FormattedText([(_EMPTY_STYLE, f"  {message}")]),
        )

    def _group_rows(self, group: str | None, *, needs_spacer: bool) -> list[Row]:
        """Return spacer + group header rows for a group."""
        if not group:
            return []
        rows: list[Row] = []
        if needs_spacer:
            rows.append(self._spacer_row())
        rows.append(self._group_row(group, self._options.group_style))
        return rows

    def render(self, state: ListState) -> list[Row]:
        """Render all rows from the current state."""
        rows: list[Row] = []

        if self._options.list_heading:
            rows.append(self._heading_row(self._options.list_heading))

        if not state.filtered_items:
            rows.append(self._empty_row(self._options.empty_message))
            return rows

        max_label_width = self._max_label_width(state.filtered_items)
        command_index = 0

        for group, items in state.grouped_items():
            rows.extend(self._group_rows(group, needs_spacer=bool(rows)))
            for item in items:
                is_selected = command_index == state.selected_index
                rows.append(
                    self._item_row(item, is_selected=is_selected, max_label_width=max_label_width)
                )
                command_index += 1

        return rows or [self._spacer_row()]
