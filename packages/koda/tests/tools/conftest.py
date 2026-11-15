"""Pytest fixtures for tools tests."""

from __future__ import annotations

from pydantic import BaseModel, Field

from koda.messages import ToolOutput
from koda.tools.exceptions import ToolError

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

    async def execute(self, params: SimpleParams) -> ToolOutput:
        return ToolOutput(content={"result": f"Hello {params.name}", "count": params.count})


class ErrorTool:
    """A tool that always raises an error."""

    name = "error_tool"
    description = "A tool that raises errors"
    parameters_model = SimpleParams

    async def execute(self, params: SimpleParams) -> ToolOutput:
        raise ToolError(f"Intentional error for {params.name}")


class CrashTool:
    """A tool that raises an unexpected exception."""

    name = "crash_tool"
    description = "A tool that raises a non-ToolError exception"
    parameters_model = SimpleParams

    async def execute(self, params: SimpleParams) -> ToolOutput:
        raise ValueError(f"Unexpected failure for {params.name}")
