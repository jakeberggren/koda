from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.tools import ToolOutput
from koda.tools.decorators import tool
from koda.tools.exceptions import ToolError
from koda.tools.files import write_text

if TYPE_CHECKING:
    from pathlib import Path

    from koda.tools.context import ToolContext


class WriteError(ToolError):
    """Failed to write file."""

    def __init__(self, path: str, *, cause: Exception) -> None:
        self.path = path
        self.cause = cause
        super().__init__(f"Failed to write '{path}': {cause}")


class WriteFileParams(BaseModel):
    """Parameters for writing a file."""

    path: str = Field(..., description="Path to the file to write")
    content: str = Field(..., description="Content to write to the file")


@tool
class WriteFileTool:
    """Tool for writing file contents."""

    name: str = "write_file"
    description: str = (
        "Write content to a file on the filesystem."
        "Only use this tool to create new files."
        "To edit existing files, use the edit_file tool."
    )
    parameters_model: type[WriteFileParams] = WriteFileParams

    async def execute(self, params: WriteFileParams, ctx: ToolContext) -> ToolOutput:
        """Execute the write_file tool."""
        resolved: Path = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)

        # Validate parent directory is also within sandbox
        ctx.policy.resolve_path(str(resolved.parent), cwd=ctx.cwd)

        async with ctx.coordinator.shared_access(), ctx.coordinator.path_lock(resolved):
            await write_text(resolved, params.path, params.content, error=WriteError)

        line_count = params.content.count("\n") + (
            1 if params.content and not params.content.endswith("\n") else 0
        )
        noun = "line" if line_count == 1 else "lines"
        display = f"Wrote {line_count} {noun}"

        return ToolOutput(content={"success": True, "path": params.path}, display=display)
