"""Tests for Overlays: the stack, what floats, and where focus goes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from prompt_toolkit.application.current import set_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import FloatContainer, Window

from koda_tui.ui.overlays import Overlays

if TYPE_CHECKING:
    from collections.abc import Iterator


class _Layout:
    def __init__(self) -> None:
        self.focused: object | None = None

    def focus(self, item: object) -> None:
        self.focused = item


class _App:
    def __init__(self) -> None:
        self.layout = _Layout()
        self.invalidated = 0

    def invalidate(self) -> None:
        self.invalidated += 1


@pytest.fixture
def app() -> Iterator[_App]:
    app = _App()
    with set_app(app):  # type: ignore
        yield app


@pytest.fixture
def root() -> FloatContainer:
    return FloatContainer(Window(), floats=[])


@pytest.fixture
def fallback() -> Buffer:
    return Buffer()


@pytest.fixture
def overlays(root: FloatContainer, fallback: Buffer) -> Overlays:
    return Overlays(root, fallback=fallback)


def test_starts_closed(overlays: Overlays) -> None:
    assert not overlays.is_open


def test_open_floats_and_focuses_only_the_top(
    app: _App, root: FloatContainer, overlays: Overlays
) -> None:
    first, second = Window(), Window()
    overlays.open(first)
    overlays.open(second)
    assert overlays.is_open
    assert [f.content for f in root.floats] == [second]
    assert app.layout.focused is second


def test_close_reveals_the_one_below(app: _App, root: FloatContainer, overlays: Overlays) -> None:
    first, second = Window(), Window()
    overlays.open(first)
    overlays.open(second)
    overlays.close()
    assert [f.content for f in root.floats] == [first]
    assert app.layout.focused is first


def test_closing_the_last_focuses_the_fallback(
    app: _App,
    root: FloatContainer,
    overlays: Overlays,
    fallback: Buffer,
) -> None:
    overlays.open(Window())
    overlays.close()
    assert not overlays.is_open
    assert root.floats == []
    assert app.layout.focused is fallback


def test_close_all_empties_the_stack(app: _App, overlays: Overlays, fallback: Buffer) -> None:
    overlays.open(Window())
    overlays.open(Window())
    overlays.close_all()
    assert not overlays.is_open
    assert app.layout.focused is fallback


def test_close_when_empty_does_nothing(overlays: Overlays) -> None:
    overlays.close()
    assert not overlays.is_open


def test_every_change_redraws(app: _App, overlays: Overlays) -> None:
    overlays.open(Window())
    overlays.close()
    assert app.invalidated == 2
