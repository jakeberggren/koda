"""Tests for Overlays: the stack, what floats, and where focus goes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import set_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings, KeyPress
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import BufferControl, FloatContainer, HSplit, Layout, Window

from koda_tui.ui.overlays import Overlays

if TYPE_CHECKING:
    from collections.abc import Iterator


class _App(Application[None]):
    """A real Application, not running, that counts its redraw requests."""

    def __init__(self, layout: Layout) -> None:
        super().__init__(layout=layout)
        self.redraws = 0

    def invalidate(self) -> None:
        self.redraws += 1


def _overlay() -> Window:
    """An overlay that can take focus."""
    return Window(BufferControl(Buffer()))


@pytest.fixture
def fallback() -> Buffer:
    return Buffer()


@pytest.fixture
def root(fallback: Buffer) -> FloatContainer:
    return FloatContainer(Window(BufferControl(fallback)), floats=[])


@pytest.fixture
def app(root: FloatContainer) -> Iterator[_App]:
    app = _App(Layout(root))
    with set_app(app):
        yield app


@pytest.fixture
def overlays(root: FloatContainer, fallback: Buffer) -> Overlays:
    return Overlays(root, fallback=fallback)


def test_starts_closed(overlays: Overlays) -> None:
    assert not overlays.is_open


def test_open_floats_and_focuses_only_the_top(
    app: _App, root: FloatContainer, overlays: Overlays
) -> None:
    first, second = _overlay(), _overlay()
    overlays.open(first)
    overlays.open(second)
    assert overlays.is_open
    assert [f.content for f in root.floats] == [second]
    assert app.layout.current_window is second


def test_close_reveals_the_one_below(app: _App, root: FloatContainer, overlays: Overlays) -> None:
    first, second = _overlay(), _overlay()
    overlays.open(first)
    overlays.open(second)
    overlays.close()
    assert [f.content for f in root.floats] == [first]
    assert app.layout.current_window is first


def test_closing_the_last_focuses_the_fallback(
    app: _App,
    root: FloatContainer,
    overlays: Overlays,
    fallback: Buffer,
) -> None:
    overlays.open(_overlay())
    overlays.close()
    assert not overlays.is_open
    assert root.floats == []
    assert app.layout.has_focus(fallback)


def test_close_all_empties_the_stack(app: _App, overlays: Overlays, fallback: Buffer) -> None:
    overlays.open(_overlay())
    overlays.open(_overlay())
    overlays.close_all()
    assert not overlays.is_open
    assert app.layout.has_focus(fallback)


@pytest.mark.usefixtures("app")
def test_close_when_empty_does_nothing(overlays: Overlays) -> None:
    overlays.close()
    assert not overlays.is_open


def test_every_change_redraws(app: _App, overlays: Overlays) -> None:
    overlays.open(_overlay())
    overlays.close()
    assert app.redraws == 2


@pytest.mark.asyncio  # The key processor schedules its flush timeout on the loop.
async def test_overlay_keys_work_for_input_that_arrives_before_the_next_render(
    app: _App, overlays: Overlays
) -> None:
    """Keys in the same read as the one that opened an overlay are handled before
    anything renders. They must still reach bindings on the overlay's containers,
    like a panel's Escape, and leave those bindings working afterwards."""
    escape = KeyBindings()
    escape.add(Keys.Escape, eager=True)(lambda _event: overlays.close())
    overlays.open(HSplit([_overlay()], key_bindings=escape))

    app.key_processor.feed_multiple([KeyPress("a"), KeyPress(Keys.Escape)])
    app.key_processor.process_keys()

    assert not overlays.is_open
