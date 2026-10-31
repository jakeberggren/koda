from pathlib import Path

import pytest

from koda_service import ServiceStatus, ServiceStatusCode
from koda_tui.state import AppState


@pytest.fixture
def ready() -> ServiceStatus:
    """A service that is ready to chat."""
    return ServiceStatus(code=ServiceStatusCode.READY, summary="Ready")


@pytest.fixture
def state(ready: ServiceStatus) -> AppState:
    """The state of a ready app, for a workspace at /workspace."""
    return AppState(workspace=Path("/workspace"), service_status=ready)
