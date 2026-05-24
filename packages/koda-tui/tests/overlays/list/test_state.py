"""Tests for ListState — pure search/filter/selection logic."""

from __future__ import annotations

import pytest

from koda_tui.overlays.list.state import ListState
from koda_tui.palette.items import ListItem


def _items(labels: list[str], **kwargs) -> list[ListItem]:
    return [ListItem(id=label.lower(), label=label, **kwargs) for label in labels]


@pytest.fixture
def three_items() -> list[ListItem]:
    return _items(["Apple", "Banana", "Cherry"])


class TestSearch:
    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("", ["Apple", "Banana", "Cherry"]),
            ("app", ["Apple"]),
            ("APP", ["Apple"]),
            ("a", ["Apple", "Banana"]),
            ("xyz", []),
        ],
    )
    def test_filters(self, three_items, query, expected) -> None:
        state = ListState(items=three_items)
        state.set_search(query)
        assert [i.label for i in state.filtered_items] == expected

    def test_resets_selection(self, three_items) -> None:
        state = ListState(items=three_items)
        state.move_selection(2)
        state.set_search("a")
        assert state.selected_index == 0


class TestSelection:
    def test_move_and_wrap(self) -> None:
        state = ListState(items=_items(["A", "B", "C"]))
        assert state.selected_index == 0

        state.move_selection(1)
        assert state.selected_index == 1

        state.move_selection(1, wrap=True)
        assert state.selected_index == 2

        state.move_selection(1, wrap=True)
        assert state.selected_index == 0  # wraps

    def test_clamped(self) -> None:
        state = ListState(items=_items(["A", "B"]))
        state.move_selection(-10)
        assert state.selected_index == 0

        state.move_selection(10)
        assert state.selected_index == 1

    def test_empty(self) -> None:
        state = ListState(items=[])
        assert state.selected_item is None
        state.move_selection(1)
        assert state.selected_index == 0


class TestGrouping:
    def test_ungrouped(self) -> None:
        state = ListState(items=_items(["A", "B"]))
        grouped = state.grouped_items()
        assert len(grouped) == 1
        assert grouped[0][0] is None
        assert [i.label for i in grouped[0][1]] == ["A", "B"]

    def test_grouped(self) -> None:
        items = [
            ListItem(id="a1", label="A1", group="Group A"),
            ListItem(id="a2", label="A2", group="Group A"),
            ListItem(id="b1", label="B1", group="Group B"),
        ]
        state = ListState(items=items)
        grouped = state.grouped_items()
        assert [g[0] for g in grouped] == ["Group A", "Group B"]

    def test_selected_item_uses_display_order(self) -> None:
        items = [
            ListItem(id="connect_provider", label="Connect Provider", group="Agent"),
            ListItem(id="set_thinking", label="Set Thinking Level", group="Agent"),
            ListItem(id="new_session", label="New Session", group="Sessions"),
            ListItem(id="list_sessions", label="List Sessions", group="Sessions"),
            ListItem(id="switch_model", label="Switch Model", group="Agent"),
            ListItem(id="toggle_theme", label="Toggle Theme", group="Appearance"),
        ]
        state = ListState(items=items)
        state.move_selection(4)
        assert state.display_items[4].id == "list_sessions"
        assert state.selected_item is state.display_items[4]

    def test_mixed(self) -> None:
        items = [
            ListItem(id="u1", label="Ungrouped"),
            ListItem(id="a1", label="A1", group="Group A"),
        ]
        state = ListState(items=items)
        grouped = state.grouped_items()
        assert grouped[0][0] is None
        assert grouped[1][0] == "Group A"

    def test_respects_search(self, three_items) -> None:
        state = ListState(items=three_items)
        state.set_search("app")
        grouped = state.grouped_items()
        assert len(grouped) == 1
        assert grouped[0][1][0].label == "Apple"
