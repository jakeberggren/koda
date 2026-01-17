from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.tools import ToolOutput, exceptions
from koda.tools.decorators import tool

if TYPE_CHECKING:
    from koda.tools.context import ToolContext


class ReadFileParams(BaseModel):
    """Parameters for reading a file."""

    path: str = Field(..., description="Path to the file to read")


@tool
class ReadFileTool:
    """Tool for reading file contents."""

    name: str = "read_file"
    description: str = "Read the contents of a file from the filesystem"
    parameters_model: type[ReadFileParams] = ReadFileParams

    async def execute(self, params: ReadFileParams, ctx: ToolContext) -> ToolOutput:
        """Execute the read_file tool."""
        resolved = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)

        if not resolved.exists():
            raise exceptions.ToolFileNotFoundError(resolved)

        if not resolved.is_file():
            raise exceptions.ToolPathTypeError(resolved, "file")

        try:
            text_content = resolved.read_text(encoding="utf-8")
        except PermissionError as e:
            raise exceptions.ToolPermissionError(resolved) from e
        except OSError as e:
            raise exceptions.ToolReadError(resolved, e) from e

        return ToolOutput(content={"text": text_content})
