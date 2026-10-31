from pathlib import Path

import pytest

from koda_service import ServiceStatus, ServiceStatusCode
from koda_tui import AppState
from koda_tui.app.conversation import Conversation

READY = ServiceStatus(code=ServiceStatusCode.READY, summary="Ready")


@pytest.fixture
def state() -> AppState:
    """An AppState for testing."""
    return AppState(workspace=Path("/workspace"), service_status=READY)


@pytest.fixture
def conversation(state: AppState) -> Conversation:
    """A Conversation over ``state``."""
    return Conversation(state)
