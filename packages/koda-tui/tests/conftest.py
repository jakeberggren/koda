from pathlib import Path

import pytest

from koda_tui.state import AppState


@pytest.fixture
def state() -> AppState:
    """The state of a ready app, for a workspace at /workspace."""
    return AppState(workspace=Path("/workspace"))
