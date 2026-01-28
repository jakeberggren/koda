from __future__ import annotations

from itertools import islice
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
    offset: int = Field(0, ge=0, description="Offset to start reading from")
    limit: int = Field(1, gt=0, description="Number of lines to read")


@tool
class ReadFileTool:
    """Tool for reading file contents."""

    name: str = "read_file"
    description: str = (
        "Read file contents (line-based). "
        "Prefer small ranges via offset/limit and expand as needed."
    )
    parameters_model: type[ReadFileParams] = ReadFileParams

    async def execute(self, params: ReadFileParams, ctx: ToolContext) -> ToolOutput:
        """Execute the read_file tool."""
        resolved = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)

        if not resolved.exists():
            raise exceptions.FileNotFoundError(params.path)

        if not resolved.is_file():
            raise exceptions.NotAFileError(params.path)

        try:
            with resolved.open("r", encoding="utf-8") as handle:
                lines = list(islice(handle, params.offset, params.offset + params.limit))
        except PermissionError as e:
            raise exceptions.PermissionError(params.path) from e
        except OSError as e:
            raise ReadError(params.path, cause=e) from e

        text_content = "".join(lines)
        line_count = len(lines)
        noun = "line" if line_count == 1 else "lines"
        display = f"Read {line_count} {noun}"

        return ToolOutput(content={"text": text_content}, display=display)
