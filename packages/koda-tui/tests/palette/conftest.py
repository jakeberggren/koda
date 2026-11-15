"""A palette context over fakes: overlays that keep what opens, and settings updates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock

import pytest

from koda.sessions import InMemorySessionStore
from koda_tui.palette.context import PaletteContext

if TYPE_CHECKING:
    from koda_tui.state import AppState
    from koda_tui.ui.overlays import Overlays as RealOverlays


class Overlays:
    """A stack of the widgets the menus open, the real ones."""

    def __init__(self) -> None:
        self.stack: list[Any] = []

    def open(self, overlay: object) -> None:
        self.stack.append(overlay)

    def close(self) -> None:
        self.stack.pop()

    def close_all(self) -> None:
        self.stack.clear()

    @property
    def top(self) -> Any:
        return self.stack[-1]

    @property
    def kinds(self) -> list[type]:
        return [type(overlay) for overlay in self.stack]

    def pick(self, label: str, picker: Any = None) -> None:
        """Choose the item labelled ``label`` in ``picker``, the top one by default."""
        picker = picker or self.top
        picker.select(next(item for item in picker.items if item.label == label))


@pytest.fixture
def overlays() -> Overlays:
    return Overlays()


@pytest.fixture
def update_settings(state: AppState) -> Mock:
    """Takes the new settings into ``state``, as the app does."""
    return Mock(side_effect=lambda settings: setattr(state, "settings", settings))


@pytest.fixture
def terminal() -> Mock:
    return Mock()


@pytest.fixture
def context(
    overlays: Overlays, update_settings: Mock, terminal: Mock, state: AppState
) -> PaletteContext:
    """A context over the fake overlays, mock ``update_settings`` and ``terminal``, and
    ``state``."""
    return PaletteContext(
        overlays=cast("RealOverlays", overlays),
        catalog=Mock(),
        credentials=Mock(),
        store=InMemorySessionStore(),
        state=state,
        update_settings=update_settings,
        outbox=Mock(),
        terminal=terminal,
    )
