"""Tests for OverlayManager — overlay stack management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from prompt_toolkit.layout import Float, Window

from koda_tui.overlays.manager import OverlayManager

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class _MockBuffer:
    """Mock buffer for focus testing."""

    name: str = "buffer"


class _MockContainer:
    """A valid prompt_toolkit container for mocks."""

    def __pt_container__(self) -> Window:
        return Window()


@dataclass
class _MockOverlay:
    """Mock overlay implementing the Overlay protocol."""

    name: str
    buffer_name: str = "search_buffer"
    search_buffer: _MockBuffer | None = None
    input_buffer: _MockBuffer | None = None

    def __post_init__(self) -> None:
        buffer = _MockBuffer(self.buffer_name)
        setattr(self, self.buffer_name, buffer)
        self.focus_target = buffer

    def __pt_container__(self) -> _MockContainer:
        return _MockContainer()


class _MockFloats:
    """Mock FloatContainer.floats list."""

    def __init__(self) -> None:
        self.items: list[Float] = []

    def clear(self) -> None:
        self.items.clear()

    def append(self, item: Float) -> None:
        self.items.append(item)

    def __len__(self) -> int:
        return len(self.items)

    def __contains__(self, item: object) -> bool:
        return item in self.items

    def __iter__(self) -> Iterator[Float]:
        return iter(self.items)


class _MockLayout:
    def __init__(self) -> None:
        self.focused: object | None = None

    def focus(self, item: object) -> None:
        self.focused = item


class _MockApp:
    def __init__(self) -> None:
        self.layout = _MockLayout()


class _MockRootContainer:
    def __init__(self) -> None:
        self.floats = _MockFloats()


@pytest.fixture
def manager():
    """OverlayManager with a mock root container."""
    root = _MockRootContainer()
    app = _MockApp()
    return OverlayManager(root, app), root, app  # type: ignore


@pytest.fixture
def manager_with_fallback():
    """OverlayManager with a fallback focus target."""
    fallback = _MockBuffer("input")
    app = _MockApp()
    root = _MockRootContainer()
    return (
        OverlayManager(root, app, fallback_focus_target=fallback),  # type: ignore
        root,
        app,
        fallback,
    )


class TestConstruction:
    def test_initially_closed(self, manager) -> None:
        manager, _root, _app = manager
        assert not manager.is_open


class TestPush:
    def test_pushes_overlay(self, manager) -> None:
        manager, _root, _app = manager
        overlay = _MockOverlay("test")
        manager.push(overlay)
        assert manager.is_open

    def test_clears_previous_float(self, manager) -> None:
        manager, root, _app = manager
        o1 = _MockOverlay("first")
        o2 = _MockOverlay("second")
        manager.push(o1)
        first_float = root.floats.items[0]
        manager.push(o2)
        assert first_float not in root.floats

    def test_focuses_search_buffer(self, manager) -> None:
        manager, _root, app = manager
        overlay = _MockOverlay("test", buffer_name="search_buffer")
        manager.push(overlay)
        assert app.layout.focused is overlay.search_buffer

    def test_focuses_input_buffer(self, manager) -> None:
        manager, _root, app = manager
        overlay = _MockOverlay("test", buffer_name="input_buffer")
        manager.push(overlay)
        assert app.layout.focused is overlay.input_buffer


class TestPop:
    def test_pop_returns_overlay(self, manager) -> None:
        manager, _root, _app = manager
        overlay = _MockOverlay("test")
        manager.push(overlay)
        result = manager.pop()
        assert result is overlay

    def test_pop_empty_returns_none(self, manager) -> None:
        manager, _root, _app = manager
        assert manager.pop() is None

    def test_pop_reveals_previous(self, manager) -> None:
        manager, root, app = manager
        o1 = _MockOverlay("first")
        o2 = _MockOverlay("second")
        manager.push(o1)
        manager.push(o2)
        manager.pop()
        assert len(root.floats) == 1
        assert app.layout.focused is o1.search_buffer

    def test_pop_closes_when_last(self, manager) -> None:
        manager, _root, _app = manager
        overlay = _MockOverlay("test")
        manager.push(overlay)
        manager.pop()
        assert not manager.is_open

    def test_pop_last_restores_fallback_focus(self, manager_with_fallback) -> None:
        manager, _root, app, fallback = manager_with_fallback
        manager.push(_MockOverlay("test"))
        manager.pop()
        assert app.layout.focused is fallback


class TestClear:
    def test_clears_all(self, manager) -> None:
        manager, root, _app = manager
        manager.push(_MockOverlay("a"))
        manager.push(_MockOverlay("b"))
        manager.clear()
        assert not manager.is_open
        assert len(root.floats) == 0

    def test_clear_empty_noop(self, manager) -> None:
        manager, _root, _app = manager
        manager.clear()
        assert not manager.is_open

    def test_clear_restores_fallback_focus(self, manager_with_fallback) -> None:
        manager, _root, app, fallback = manager_with_fallback
        manager.push(_MockOverlay("test"))
        manager.clear()
        assert app.layout.focused is fallback
