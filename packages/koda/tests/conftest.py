"""Pytest configuration and shared fixtures."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from pydantic import BaseModel

from koda.harness.toolbox.workspace import Workspace
from koda.tools import base as tools_base


class MockToolParams(BaseModel):
    """Simple parameters model for testing."""

    query: str
    limit: int = 10


@pytest.fixture
def sample_tool_definition() -> tools_base.ToolDefinition:
    """A minimal tool definition for contract tests."""
    return tools_base.ToolDefinition(
        name="search",
        description="Search for information",
        parameters_model=MockToolParams,
    )


@pytest.fixture
def workspace_dir() -> Generator[Path]:
    """A temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Resolve to handle macOS /var -> /private/var symlink
        yield Path(tmpdir).resolve()


@pytest.fixture
def workspace(workspace_dir: Path) -> Workspace:
    """A workspace in the temporary directory."""
    return Workspace(workspace_dir)
