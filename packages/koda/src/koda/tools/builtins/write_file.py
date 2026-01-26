from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.tools import ToolOutput, exceptions
from koda.tools.decorators import tool

if TYPE_CHECKING:
    from koda.tools.context import ToolContext


class WriteError(exceptions.ToolError):
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
    description: str = "Write content to a file on the filesystem"
    parameters_model: type[WriteFileParams] = WriteFileParams

    async def execute(self, params: WriteFileParams, ctx: ToolContext) -> ToolOutput:
        """Execute the write_file tool."""
        resolved = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)

        # Validate parent directory is also within sandbox
        ctx.policy.resolve_path(str(resolved.parent), cwd=ctx.cwd)

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(params.content, encoding="utf-8")
        except PermissionError as e:
            raise exceptions.PermissionError(params.path) from e
        except OSError as e:
            raise WriteError(params.path, cause=e) from e

        line_count = params.content.count("\n") + (
            1 if params.content and not params.content.endswith("\n") else 0
        )
        noun = "line" if line_count == 1 else "lines"
        display = f"Wrote {line_count} {noun}"

        return ToolOutput(content={"success": True, "path": params.path}, display=display)
