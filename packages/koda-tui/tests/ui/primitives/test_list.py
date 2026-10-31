"""Tests for the List primitive: ListState (search, selection, grouping) and rendered rows."""

from __future__ import annotations

import pytest

from koda_tui.appearance import Tokens, compose
from koda_tui.ui.primitives import List, ListItem, ListState
from koda_tui.ui.primitives.list import Row, RowKind


def _items(labels: list[str], **kwargs) -> list[ListItem]:
    return [ListItem(data=label.lower(), label=label, **kwargs) for label in labels]


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
        state = ListState(three_items)
        state.set_search(query)
        assert [i.label for i in state.filtered_items] == expected

    def test_resets_selection(self, three_items) -> None:
        state = ListState(three_items)
        state.move_selection(2)
        state.set_search("a")
        assert state.selected_index == 0


class TestSelection:
    def test_move_and_wrap(self) -> None:
        state = ListState(_items(["A", "B", "C"]))
        assert state.selected_index == 0

        state.move_selection(1)
        assert state.selected_index == 1

        state.move_selection(1, wrap=True)
        assert state.selected_index == 2

        state.move_selection(1, wrap=True)
        assert state.selected_index == 0  # wraps

    def test_clamped(self) -> None:
        state = ListState(_items(["A", "B"]))
        state.move_selection(-10)
        assert state.selected_index == 0

        state.move_selection(10)
        assert state.selected_index == 1

    def test_empty(self) -> None:
        state = ListState([])
        assert state.selected_item is None
        state.move_selection(1)
        assert state.selected_index == 0


class TestGrouping:
    def test_ungrouped(self) -> None:
        state = ListState(_items(["A", "B"]))
        grouped = state.grouped_items()
        assert len(grouped) == 1
        assert grouped[0][0] is None
        assert [i.label for i in grouped[0][1]] == ["A", "B"]

    def test_grouped(self) -> None:
        items = [
            ListItem(data="a1", label="A1", group="Group A"),
            ListItem(data="a2", label="A2", group="Group A"),
            ListItem(data="b1", label="B1", group="Group B"),
        ]
        state = ListState(items)
        grouped = state.grouped_items()
        assert [g[0] for g in grouped] == ["Group A", "Group B"]

    def test_selected_item_uses_display_order(self) -> None:
        items = [
            ListItem(data="connect_provider", label="Connect Provider", group="Agent"),
            ListItem(data="set_thinking", label="Set Thinking Level", group="Agent"),
            ListItem(data="new_session", label="New Session", group="Sessions"),
            ListItem(data="list_sessions", label="List Sessions", group="Sessions"),
            ListItem(data="switch_model", label="Switch Model", group="Agent"),
            ListItem(data="select_theme", label="Select Theme", group="Appearance"),
        ]
        state = ListState(items)
        state.move_selection(4)
        assert state.display_items[4].data == "list_sessions"
        assert state.selected_item is state.display_items[4]

    def test_mixed(self) -> None:
        items = [
            ListItem(data="u1", label="Ungrouped"),
            ListItem(data="a1", label="A1", group="Group A"),
        ]
        state = ListState(items)
        grouped = state.grouped_items()
        assert grouped[0][0] is None
        assert grouped[1][0] == "Group A"

    def test_respects_search(self, three_items) -> None:
        state = ListState(three_items)
        state.set_search("app")
        grouped = state.grouped_items()
        assert len(grouped) == 1
        assert grouped[0][1][0].label == "Apple"


def _item(label: str, **kwargs) -> ListItem:
    return ListItem(data=label.lower(), label=label, **kwargs)


def _item_label(row: Row) -> str:
    """The label of an item row: its second fragment, after the marker."""
    return row.text[1][1].strip()


class TestRows:
    def test_renders_items(self) -> None:
        state = ListState([_item("Apple"), _item("Banana")])
        rows = List(state).rows()
        item_rows = [r for r in rows if r.kind == RowKind.ITEM]
        assert [_item_label(r) for r in item_rows] == ["Apple", "Banana"]

    def test_selected_style(self) -> None:
        state = ListState([_item("A"), _item("B")])
        state.move_selection(1)
        rows = List(state).rows()
        item_rows = [r for r in rows if r.kind == RowKind.ITEM]
        assert item_rows[0].text[0] == (Tokens.Text.DEFAULT, "  ")
        assert item_rows[1].text[0] == (compose(Tokens.Surface.SELECTED, Tokens.Text.STRONG), "- ")

    @pytest.mark.parametrize("selected", [True, False])
    def test_current_item_style(self, selected) -> None:
        items = [_item("A"), _item("B", current=True)]
        state = ListState(items)
        if selected:
            state.move_selection(1)
        rows = List(state).rows()
        item_rows = [r for r in rows if r.kind == RowKind.ITEM]
        expected_marker_style = (
            compose(Tokens.Surface.SELECTED, Tokens.Text.STRONG)
            if selected
            else compose(Tokens.Text.ACCENT, Tokens.Text.STRONG)
        )
        expected_label_style = (
            compose(Tokens.Surface.SELECTED, Tokens.Text.STRONG)
            if selected
            else compose(Tokens.Text.ACCENT, Tokens.Text.STRONG)
        )
        assert item_rows[1].text[0] == (expected_marker_style, "* ")
        assert item_rows[1].text[1][0] == expected_label_style

    def test_marker_without_current_keeps_label_style(self) -> None:
        rows = List(ListState([_item("A"), _item("B", marker="✓")])).rows()
        assert rows[1].text[0] == (compose(Tokens.Text.ACCENT, Tokens.Text.STRONG), "✓ ")
        assert rows[1].text[1][0] == Tokens.Text.DEFAULT

    def test_empty(self) -> None:
        rows = List(ListState([])).rows()
        empty = [r for r in rows if r.kind == RowKind.EMPTY]
        assert len(empty) == 1
        assert "No results found" in str(empty[0].text)

    def test_custom_empty_message(self) -> None:
        rows = List(ListState([]), empty_message="Nothing").rows()
        assert "Nothing" in str(rows[0].text)


class TestGroupedRows:
    def test_group_header(self) -> None:
        state = ListState(
            [
                _item("A1", group="Group A"),
                _item("A2", group="Group A"),
            ]
        )
        rows = List(state).rows()
        kinds = [r.kind for r in rows]
        assert kinds == [RowKind.GROUP, RowKind.ITEM, RowKind.ITEM]

    def test_heading(self) -> None:
        state = ListState([_item("Apple")])
        rows = List(state, heading="Fruits").rows()
        assert rows[0].kind == RowKind.HEADING
        assert "Fruits" in str(rows[0].text)


class TestSearchedRows:
    def test_filtered_only(self) -> None:
        state = ListState([_item("Apple"), _item("Banana")])
        state.set_search("app")
        rows = List(state).rows()
        item_rows = [r for r in rows if r.kind == RowKind.ITEM]
        assert len(item_rows) == 1
        assert _item_label(item_rows[0]) == "Apple"


def test_label_width_cuts_longer_labels_with_an_ellipsis() -> None:
    state = ListState(_items(["claude-opus-5-5-with-a-long-name", "short"]))
    rows = List(state, label_width=10).rows()
    labels = ["".join(text for _, text, *_ in row.text) for row in rows]
    assert labels[0].startswith("- claude-...")
    assert labels[1].startswith("  short     ")
