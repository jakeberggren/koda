"""Tests for the Picker widget: searching, moving, picking and shortcuts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.keys import Keys

from koda_tui.ui.primitives import ListItem
from koda_tui.ui.widgets import Picker

if TYPE_CHECKING:
    from collections.abc import Callable


def _items(*labels: str) -> list[ListItem]:
    return [ListItem(data=label, label=label) for label in labels]


def _picker(
    items: list[ListItem],
    shortcuts: dict[str, Callable[[ListItem | None], None]] | None = None,
) -> tuple[Picker, list[ListItem], list[None]]:
    picked: list[ListItem] = []
    closed: list[None] = []
    picker = Picker(
        "Pick",
        items,
        on_select=picked.append,
        on_close=lambda: closed.append(None),
        shortcuts=shortcuts,
    )
    return picker, picked, closed


def _press(picker: Picker, *keys: Keys | str) -> None:
    bindings = picker.__pt_container__().key_bindings
    handler: Callable = bindings.get_bindings_for_keys(keys)[-1].handler
    handler(None)


def test_typing_filters_the_items() -> None:
    picker, _, _ = _picker(_items("Apple", "Banana", "Cherry"))
    picker.search.text = "an"
    assert [item.label for item in picker.state.filtered_items] == ["Banana"]


def test_enter_picks_the_selected_item() -> None:
    picker, picked, _ = _picker(_items("Apple", "Banana"))
    _press(picker, Keys.Down)
    _press(picker, Keys.Enter)
    assert [item.label for item in picked] == ["Banana"]


def test_up_and_down_wrap_around() -> None:
    picker, _, _ = _picker(_items("A", "B"))
    _press(picker, Keys.Up)
    assert picker.state.selected_index == 1
    _press(picker, Keys.Down)
    assert picker.state.selected_index == 0


def test_enter_with_no_matches_picks_nothing() -> None:
    picker, picked, _ = _picker(_items("Apple"))
    picker.search.text = "zzz"
    _press(picker, Keys.Enter)
    assert picked == []


def test_escape_closes() -> None:
    picker, _, closed = _picker(_items("Apple"))
    _press(picker, Keys.Escape)
    assert closed == [None]


def test_shortcuts_act_on_the_selected_item() -> None:
    acted: list[ListItem | None] = []
    picker, _, _ = _picker(_items("Apple", "Banana"), {"c-d": acted.append})
    _press(picker, Keys.Down)
    _press(picker, "c-d")
    assert [item.label for item in acted if item] == ["Banana"]
