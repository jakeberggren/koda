from pathlib import Path

import pytest

from koda_service import ServiceStatus, ServiceStatusCode
from koda_tui.messaging import Conversation
from koda_tui.state import AppState

READY = ServiceStatus(code=ServiceStatusCode.READY, summary="Ready")


@pytest.fixture
def state() -> AppState:
    """An AppState for testing."""
    return AppState(workspace=Path("/workspace"), service_status=READY)


@pytest.fixture
def conversation(state: AppState) -> Conversation:
    """A Conversation over ``state``."""
    return Conversation(state)
