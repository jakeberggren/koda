"""Tests for PaletteOverlay — single-select searchable palette widget."""

# ruff: noqa: SLF001 - allow private member access for tests

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from koda_tui.palette.items import ListItem
from koda_tui.palette.overlay import PaletteOverlay

if TYPE_CHECKING:
    from collections.abc import Callable


def _items(labels: list[str]) -> list[ListItem]:
    return [ListItem(id=label.lower(), label=label) for label in labels]


@pytest.fixture
def palette_factory():
    """Factory that returns a configured PaletteOverlay."""
    calls = {"select": [], "close": [], "invalidate": []}

    def _make(
        items: list[ListItem] | None = None,
        on_select: Callable[[ListItem], None] | None = None,
        on_close: Callable[[], None] | None = None,
        invalidate: Callable[[], None] | None = None,
        **kwargs,
    ) -> tuple[PaletteOverlay, dict]:
        p = PaletteOverlay(
            items=items or [],
            on_select=on_select or (calls["select"].append),
            on_close=on_close or (lambda: calls["close"].append(None)),
            invalidate=invalidate or (lambda: calls["invalidate"].append(None)),
            **kwargs,
        )
        return p, calls

    return _make


class TestConstruction:
    def test_defaults(self, palette_factory) -> None:
        p, _ = palette_factory()
        assert p._title == "Commands"
        assert p._state.filtered_items == []
        assert p.search_buffer is not None

    def test_custom_title(self, palette_factory) -> None:
        p, _ = palette_factory(title="Models")
        assert p._title == "Models"

    def test_with_items(self, palette_factory) -> None:
        p, _ = palette_factory(items=_items(["Apple", "Banana"]))
        assert len(p._state.filtered_items) == 2

    def test_calculates_size_from_terminal(self, monkeypatch, palette_factory) -> None:
        monkeypatch.setattr(
            "koda_tui.palette.overlay.shutil.get_terminal_size",
            lambda *_, **__: os.terminal_size((140, 50)),
        )
        p, _ = palette_factory(items=_items(["Apple"]))
        assert p.preferred_width == 70
        assert p._height == 20

    def test_explicit_size_overrides_terminal_size(self, palette_factory) -> None:
        p, _ = palette_factory(items=_items(["Apple"]), width=42, height=7)
        assert p.preferred_width == 42
        assert p._height == 7


class TestSearch:
    def test_filters_items(self, palette_factory) -> None:
        p, _ = palette_factory(items=_items(["Apple", "Banana", "Cherry"]))
        p.search_buffer.text = "app"
        p.search_buffer.on_text_changed.fire()
        assert [i.label for i in p._state.filtered_items] == ["Apple"]

    def test_triggers_invalidate(self, palette_factory) -> None:
        calls = []
        p, _ = palette_factory(
            items=_items(["Apple"]),
            invalidate=lambda: calls.append(None),
        )
        p.search_buffer.text = "a"
        p.search_buffer.on_text_changed.fire()
        assert len(calls) >= 1

    def test_resets_selection(self, palette_factory) -> None:
        p, _ = palette_factory(items=_items(["Apple", "Banana"]))
        p._state.move_selection(1)
        p.search_buffer.text = "app"
        p.search_buffer.on_text_changed.fire()
        assert p._state.selected_index == 0


class TestSelection:
    def test_move(self, palette_factory) -> None:
        p, _ = palette_factory(items=_items(["A", "B", "C"]))
        p._move_selection(1)
        assert p._state.selected_index == 1
        p._move_selection(-1)
        assert p._state.selected_index == 0

    def test_wrap(self, palette_factory) -> None:
        p, _ = palette_factory(items=_items(["A", "B"]))
        p._move_selection(1)
        p._move_selection(1)
        assert p._state.selected_index == 0

    def test_empty(self, palette_factory) -> None:
        p, _ = palette_factory(items=[])
        assert p._selected_item is None


class TestCallbacks:
    def test_execute_selected(self, palette_factory) -> None:
        selected = []
        p, _ = palette_factory(
            items=_items(["Apple", "Banana"]),
            on_select=selected.append,
        )
        p._execute_selected()
        assert len(selected) == 1
        assert selected[0].label == "Apple"

    def test_execute_noop_when_empty(self, palette_factory) -> None:
        selected = []
        p, _ = palette_factory(
            items=[],
            on_select=selected.append,
        )
        p._execute_selected()
        assert selected == []


class TestContainer:
    def test_returns_frame(self, palette_factory) -> None:
        p, _ = palette_factory(items=_items(["Apple"]))
        container = p.__pt_container__()
        assert container.__class__.__name__ == "Frame"

    def test_shortcuts_registered(self, palette_factory) -> None:
        p, _ = palette_factory(
            items=_items(["Apple"]),
            shortcuts={"c-n": lambda _: None},
        )
        assert "c-n" in p._shortcuts


class TestKeybindings:
    def test_escape_calls_close(self, palette_factory) -> None:
        closed = []
        p, _ = palette_factory(
            items=_items(["Apple"]),
            on_close=lambda: closed.append(None),
        )
        p._on_escape(None)
        assert len(closed) == 1

    def test_enter_calls_select(self, palette_factory) -> None:
        selected = []
        p, _ = palette_factory(
            items=_items(["Apple"]),
            on_select=selected.append,
        )
        p._on_enter(None)
        assert len(selected) == 1
        assert selected[0].label == "Apple"

    def test_up_moves_selection(self, palette_factory) -> None:
        p, _ = palette_factory(items=_items(["A", "B"]))
        p._state.move_selection(1)
        assert p._state.selected_index == 1
        p._on_up(None)
        assert p._state.selected_index == 0

    def test_down_moves_selection(self, palette_factory) -> None:
        p, _ = palette_factory(items=_items(["A", "B"]))
        assert p._state.selected_index == 0
        p._on_down(None)
        assert p._state.selected_index == 1
