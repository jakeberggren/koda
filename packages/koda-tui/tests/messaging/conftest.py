import pytest

from koda_tui.messaging import Conversation
from koda_tui.state import AppState


@pytest.fixture
def conversation(state: AppState) -> Conversation:
    """A Conversation over ``state``."""
    return Conversation(state)
