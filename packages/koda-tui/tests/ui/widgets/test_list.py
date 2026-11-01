"""Tests for the List widget: ListState (search, selection, grouping) and its lines."""

from __future__ import annotations

import pytest
from prompt_toolkit.formatted_text import fragment_list_to_text
from prompt_toolkit.utils import get_cwidth

from koda_tui import strings
from koda_tui.appearance import Tokens, compose
from koda_tui.ui.widgets import List, ListItem, ListState
from koda_tui.ui.widgets.list import EMPTY_STYLE, GROUP_STYLE


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


def _label(line: list) -> str:
    """The label of an item line: its second fragment, after the marker."""
    return line[1][1].strip()


SELECTED = compose(Tokens.Surface.SELECTED, Tokens.Text.STRONG)
CURRENT = compose(Tokens.Text.ACCENT, Tokens.Text.STRONG)


class TestLines:
    def test_renders_items(self) -> None:
        lines = List(ListState([_item("Apple"), _item("Banana")])).lines()
        assert [_label(line) for line in lines.lines] == ["Apple", "Banana"]

    def test_selected_style(self) -> None:
        state = ListState([_item("A"), _item("B")])
        state.move_selection(1)
        lines = List(state).lines()
        assert lines.lines[0][0] == (Tokens.Text.DEFAULT, "  ")
        assert lines.lines[1][0] == (SELECTED, "- ")
        assert lines.selected == 1

    @pytest.mark.parametrize("selected", [True, False])
    def test_current_item_style(self, selected) -> None:
        state = ListState([_item("A"), _item("B", current=True)])
        if selected:
            state.move_selection(1)
        line = List(state).lines().lines[1]
        style = SELECTED if selected else CURRENT
        assert line[0] == (style, "* ")
        assert line[1][0] == style

    def test_marker_without_current_keeps_label_style(self) -> None:
        lines = List(ListState([_item("A"), _item("B", marker="✓")])).lines().lines
        assert lines[1][0] == (CURRENT, "✓ ")
        assert lines[1][1][0] == Tokens.Text.DEFAULT

    def test_empty(self) -> None:
        lines = List(ListState([])).lines()
        assert lines.lines == [[(EMPTY_STYLE, f"  {strings.Common.NO_MATCHES}")]]
        assert lines.selected is None

    def test_custom_empty_message(self) -> None:
        lines = List(ListState([]), empty_message="Nothing").lines()
        assert fragment_list_to_text(lines.lines[0]) == "  Nothing"


class TestGroupedLines:
    def test_group_header_is_the_selected_items_anchor(self) -> None:
        state = ListState([_item("A1", group="Group A"), _item("A2", group="Group A")])
        state.move_selection(1)
        lines = List(state).lines()
        assert lines.lines[0] == [(GROUP_STYLE, "Group A")]
        assert [_label(line) for line in lines.lines[1:]] == ["A1", "A2"]
        assert (lines.selected, lines.anchor) == (2, 0)

    def test_groups_are_a_blank_line_apart(self) -> None:
        state = ListState([_item("U"), _item("A1", group="Group A")])
        state.move_selection(1)
        lines = List(state).lines()
        assert lines.lines[1:3] == [[], [(GROUP_STYLE, "Group A")]]
        assert (lines.selected, lines.anchor) == (3, 2)

    def test_ungrouped_items_have_no_anchor(self) -> None:
        lines = List(ListState([_item("Apple")]), heading="Fruits").lines()
        assert lines.lines[0] == [(GROUP_STYLE, "Fruits")]
        assert (lines.selected, lines.anchor) == (1, None)

    def test_heading_is_spaced_from_the_first_group(self) -> None:
        lines = List(ListState([_item("A1", group="Group A")]), heading="Fruits").lines()
        assert lines.lines[:3] == [[(GROUP_STYLE, "Fruits")], [], [(GROUP_STYLE, "Group A")]]


class TestSearchedLines:
    def test_filtered_only(self) -> None:
        state = ListState([_item("Apple"), _item("Banana")])
        state.set_search("app")
        lines = List(state).lines().lines
        assert [_label(line) for line in lines] == ["Apple"]


def test_label_width_cuts_longer_labels_with_an_ellipsis() -> None:
    state = ListState(_items(["claude-opus-5-5-with-a-long-name", "short"]))
    lines = List(state, label_width=10).lines().lines
    labels = [fragment_list_to_text(line) for line in lines]
    assert labels[0].startswith("- claude-...")
    assert labels[1].startswith("  short     ")


def test_labels_are_padded_and_cut_by_cells_not_characters() -> None:
    # Each of these characters takes two cells.
    state = ListState(_items(["日本語のモデル", "ab"]))
    lines = List(state, label_width=6).lines().lines
    labels = [line[1][1] for line in lines]
    assert labels == ["日... ", "ab    "]  # 日本... would take 7 cells.
    assert all(get_cwidth(label) == 6 for label in labels)
