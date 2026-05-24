"""Pure list state: search, filter, selection, grouping."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from koda_tui.palette.items import ListItem


@dataclass
class ListState:
    """
    Mutable state for a searchable, selectable list. Manages
    Search/filtering, Selection index and Grouping of items.
    """

    items: list[ListItem] = field(default_factory=list)
    search_text: str = ""
    selected_index: int = 0

    _filtered_items: list[ListItem] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._filtered_items = list(self.items)

    def set_search(self, text: str) -> None:
        """Filter items by search text and reset selection."""
        self.search_text = text.lower()
        if not self.search_text:
            self._filtered_items = list(self.items)
        else:
            self._filtered_items = [
                item for item in self.items if self.search_text in item.label.lower()
            ]
        self.selected_index = 0

    @property
    def filtered_items(self) -> list[ListItem]:
        return self._filtered_items

    @property
    def selected_item(self) -> ListItem | None:
        """Return the selected item in visual display order."""
        display_items = self.display_items
        if not display_items:
            return None
        index = max(0, min(self.selected_index, len(display_items) - 1))
        return display_items[index]

    @property
    def display_items(self) -> list[ListItem]:
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

    def grouped_items(self) -> list[tuple[str | None, list[ListItem]]]:
        """Return items grouped by their group label."""
        grouped: list[tuple[str | None, list[ListItem]]] = []
        group_map: dict[str, list[ListItem]] = {}
        ungrouped: list[ListItem] = []

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
