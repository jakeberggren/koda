"""Pytest configuration and shared fixtures."""

import pytest

from koda_tui.app import AppState
from koda_tui.rendering import RichToPromptToolkit


@pytest.fixture
def converter() -> RichToPromptToolkit:
    """A RichToPromptToolkit converter for testing."""
    return RichToPromptToolkit(width=80)


@pytest.fixture
def state() -> AppState:
    """An AppState for testing."""
    return AppState(provider_name="test", model_name="test-model")
