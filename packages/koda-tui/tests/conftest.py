from pathlib import Path

import pytest

from koda_tui import AppState
from koda_tui.app.response import ResponseLifecycle
from koda_tui.rendering import MessageRenderer
from koda_tui.theme import TerminalTheme


@pytest.fixture
def converter() -> MessageRenderer:
    """A MessageRenderer converter for testing."""
    return MessageRenderer(TerminalTheme(theme="dark", surface=(18, 52, 86)), width=80)


@pytest.fixture
def state() -> AppState:
    """An AppState for testing."""
    return AppState(
        provider_id="test",
        workspace_root=Path("/workspace"),
    )


@pytest.fixture
def lifecycle(state: AppState) -> ResponseLifecycle:
    """A ResponseLifecycle for testing."""
    return ResponseLifecycle(state)
