"""Pytest fixtures for tools tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, Field

from koda.tools import FileCoordinator, ToolContext, ToolOutput, ToolRegistry
from koda.tools.exceptions import ToolError
from koda.tools.policy import ToolPolicy

if TYPE_CHECKING:
    from collections.abc import Generator


# ==============================================================================
# Test Parameter Models
# ==============================================================================


class SimpleParams(BaseModel):
    """Simple parameters for testing."""

    name: str = Field(..., description="A name")
    count: int = Field(default=1, description="A count")


class ComplexParams(BaseModel):
    """Complex parameters with nested types."""

    items: list[str] = Field(default_factory=list, description="List of items")
    options: dict[str, int] = Field(default_factory=dict, description="Options map")


# ==============================================================================
# Test Tool Implementations
# ==============================================================================


class SimpleTool:
    """A simple test tool."""

    name = "simple_tool"
    description = "A simple test tool"
    parameters_model = SimpleParams

    async def execute(self, params: SimpleParams, ctx: ToolContext) -> ToolOutput:
        return ToolOutput(content={"result": f"Hello {params.name}", "count": params.count})


class ErrorTool:
    """A tool that always raises an error."""

    name = "error_tool"
    description = "A tool that raises errors"
    parameters_model = SimpleParams

    async def execute(self, params: SimpleParams, ctx: ToolContext) -> ToolOutput:
        raise ToolError(f"Intentional error for {params.name}")


class CrashTool:
    """A tool that raises an unexpected exception."""

    name = "crash_tool"
    description = "A tool that raises a non-ToolError exception"
    parameters_model = SimpleParams

    async def execute(self, params: SimpleParams, ctx: ToolContext) -> ToolOutput:
        raise ValueError(f"Unexpected failure for {params.name}")


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def sandbox_dir() -> Generator[Path]:
    """Create a temporary sandbox directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Resolve to handle macOS /var -> /private/var symlink
        yield Path(tmpdir).resolve()


@pytest.fixture
def policy(sandbox_dir: Path) -> ToolPolicy:
    """Create a ToolPolicy for testing."""
    return ToolPolicy.create(sandbox_dir)


@pytest.fixture
def context(sandbox_dir: Path, policy: ToolPolicy) -> ToolContext:
    """Create a ToolContext for testing."""
    return ToolContext(cwd=sandbox_dir, policy=policy, files=FileCoordinator())


@pytest.fixture
def registry() -> ToolRegistry:
    """Create an empty ToolRegistry."""
    return ToolRegistry()


@pytest.fixture
def simple_tool() -> SimpleTool:
    """Create a SimpleTool instance."""
    return SimpleTool()


@pytest.fixture
def error_tool() -> ErrorTool:
    """Create an ErrorTool instance."""
    return ErrorTool()


@pytest.fixture
def crash_tool() -> CrashTool:
    """Create a CrashTool instance."""
    return CrashTool()
