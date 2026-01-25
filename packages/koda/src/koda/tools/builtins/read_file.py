from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.tools import ToolOutput, exceptions
from koda.tools.decorators import tool

if TYPE_CHECKING:
    from koda.tools.context import ToolContext


class ReadError(exceptions.ToolError):
    """Failed to read file."""

    def __init__(self, path: str, *, cause: Exception) -> None:
        self.path = path
        self.cause = cause
        super().__init__(f"Failed to read '{path}': {cause}")


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
            raise exceptions.FileNotFoundError(params.path)

        if not resolved.is_file():
            raise exceptions.NotAFileError(params.path)

        try:
            text_content = resolved.read_text(encoding="utf-8")
        except PermissionError as e:
            raise exceptions.PermissionError(params.path) from e
        except OSError as e:
            raise ReadError(params.path, cause=e) from e

        line_count = text_content.count("\n") + (
            1 if text_content and not text_content.endswith("\n") else 0
        )
        display = f"Read {line_count} lines from {params.path}"

        return ToolOutput(content={"text": text_content}, display=display)
