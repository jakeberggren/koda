"""A palette context over fakes: overlays that record what opens, and settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import Mock

import pytest

from koda_tui.palette import context as context_module
from koda_tui.palette.context import PaletteContext

if TYPE_CHECKING:
    from koda_tui.state import AppState
    from koda_tui.ui.overlays import Overlays as RealOverlays


class Overlays:
    """A stack of what was opened; a picker is recorded as its arguments."""

    def __init__(self) -> None:
        self.stack: list[dict] = []

    def open(self, overlay: dict) -> None:
        self.stack.append(overlay)

    def close(self) -> None:
        self.stack.pop()

    def close_all(self) -> None:
        self.stack.clear()

    def pick(self, label: str) -> None:
        """Choose the item labelled ``label`` in the top picker."""
        top = self.stack[-1]
        top["on_select"](next(item for item in top["items"] if item.label == label))


@pytest.fixture(autouse=True)
def _record_pickers(monkeypatch: pytest.MonkeyPatch) -> None:
    def picker(title: str, items: list, **fields: object) -> dict:
        return {"title": title, "items": items, **fields}

    monkeypatch.setattr(context_module, "Picker", picker)


@pytest.fixture
def overlays() -> Overlays:
    return Overlays()


@pytest.fixture
def settings() -> Mock:
    return Mock()


@pytest.fixture
def terminal() -> Mock:
    return Mock()


@pytest.fixture
def context(overlays: Overlays, settings: Mock, terminal: Mock, state: AppState) -> PaletteContext:
    """A context over the fake overlays, mock ``settings`` and ``terminal``, and ``state``."""
    return PaletteContext(
        overlays=cast("RealOverlays", overlays),
        service=Mock(),
        settings=settings,
        state=state,
        conversation=Mock(),
        outbox=Mock(),
        terminal=terminal,
    )
