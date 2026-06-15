"""Tests for ListRenderer — pure row rendering logic."""

from __future__ import annotations

import pytest

from koda_tui.overlays.list.renderer import ListRenderer, RenderOptions, Row, RowKind
from koda_tui.overlays.list.state import ListState
from koda_tui.palette.items import ListItem


def _item(label: str, **kwargs) -> ListItem:
    return ListItem(id=label.lower(), label=label, **kwargs)


def _item_label(row: Row) -> str:
    assert row.item is not None
    return row.item.label


class TestBasics:
    def test_renders_items(self) -> None:
        state = ListState(items=[_item("Apple"), _item("Banana")])
        rows = ListRenderer().render(state)
        item_rows = [r for r in rows if r.kind == RowKind.ITEM]
        assert [_item_label(r) for r in item_rows] == ["Apple", "Banana"]

    def test_selected_style(self) -> None:
        state = ListState(items=[_item("A"), _item("B")])
        state.move_selection(1)
        rows = ListRenderer().render(state)
        item_rows = [r for r in rows if r.kind == RowKind.ITEM]
        assert item_rows[0].text[0] == ("class:palette.item", "  ")
        assert item_rows[1].text[0] == ("class:palette.selected", "- ")

    @pytest.mark.parametrize("selected", [True, False])
    def test_marker_style(self, selected) -> None:
        items = [
            _item("A"),
            _item("B", marker="*", marker_style="class:palette.current"),
        ]
        state = ListState(items=items)
        if selected:
            state.move_selection(1)
        rows = ListRenderer().render(state)
        item_rows = [r for r in rows if r.kind == RowKind.ITEM]
        expected_marker_style = "class:palette.selected" if selected else "class:palette.marker"
        expected_label_style = "class:palette.selected" if selected else "class:palette.current"
        assert item_rows[1].text[0][0] == expected_marker_style
        assert item_rows[1].text[1][0] == expected_label_style

    def test_empty(self) -> None:
        rows = ListRenderer().render(ListState(items=[]))
        empty = [r for r in rows if r.kind == RowKind.EMPTY]
        assert len(empty) == 1
        assert "No results found" in str(empty[0].text)

    def test_custom_empty_message(self) -> None:
        rows = ListRenderer(RenderOptions(empty_message="Nothing")).render(ListState(items=[]))
        assert "Nothing" in str(rows[0].text)


class TestGrouping:
    def test_group_header(self) -> None:
        state = ListState(
            items=[
                _item("A1", group="Group A"),
                _item("A2", group="Group A"),
            ]
        )
        rows = ListRenderer().render(state)
        kinds = [r.kind for r in rows]
        assert kinds == [RowKind.GROUP, RowKind.ITEM, RowKind.ITEM]

    def test_heading(self) -> None:
        state = ListState(items=[_item("Apple")])
        rows = ListRenderer(RenderOptions(list_heading="Fruits")).render(state)
        assert rows[0].kind == RowKind.HEADING
        assert "Fruits" in str(rows[0].text)


class TestSearch:
    def test_filtered_only(self) -> None:
        state = ListState(items=[_item("Apple"), _item("Banana")])
        state.set_search("app")
        rows = ListRenderer().render(state)
        item_rows = [r for r in rows if r.kind == RowKind.ITEM]
        assert len(item_rows) == 1
        assert _item_label(item_rows[0]) == "Apple"
