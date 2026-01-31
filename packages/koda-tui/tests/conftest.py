import pytest

from koda_tui import AppState
from koda_tui.rendering import MessageRenderer


@pytest.fixture
def converter() -> MessageRenderer:
    """A MessageRenderer converter for testing."""
    return MessageRenderer(width=80)


@pytest.fixture
def state() -> AppState:
    """An AppState for testing."""
    return AppState(provider_name="test", model_name="test-model")
