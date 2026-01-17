from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.tools import ToolOutput, exceptions
from koda.tools.decorators import tool

if TYPE_CHECKING:
    from koda.tools.context import ToolContext


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
            raise exceptions.ToolPermissionError(resolved) from e
        except OSError as e:
            raise exceptions.ToolWriteError(resolved, e) from e

        return ToolOutput(content={"success": True, "path": str(resolved)})
