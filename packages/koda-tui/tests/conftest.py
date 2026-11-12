from pathlib import Path

import pytest

from koda_tui.state import AppState


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty home, so tests never read or write the user's ~/.koda."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def state() -> AppState:
    """The state of a ready app, for a workspace at /workspace."""
    return AppState(workspace=Path("/workspace"))
