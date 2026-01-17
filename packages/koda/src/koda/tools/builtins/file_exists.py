from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.tools import ToolOutput
from koda.tools.decorators import tool

if TYPE_CHECKING:
    from koda.tools.context import ToolContext


class FileExistsParams(BaseModel):
    """Parameters for checking if a file exists."""

    path: str = Field(..., description="Path to check")


@tool
class FileExistsTool:
    """Tool for checking if a file exists."""

    name: str = "file_exists"
    description: str = "Check if a file or directory exists"
    parameters_model: type[FileExistsParams] = FileExistsParams

    async def execute(self, params: FileExistsParams, ctx: ToolContext) -> ToolOutput:
        """Execute the file_exists tool."""
        resolved = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)

        exists = resolved.exists()
        return ToolOutput(content={"exists": exists, "path": str(resolved)})
