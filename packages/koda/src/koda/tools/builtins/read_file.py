from __future__ import annotations

from typing import TYPE_CHECKING

from anyio import Path as AnyioPath
from pydantic import BaseModel, Field

from koda.tools import ToolOutput
from koda.tools.decorators import tool
from koda.tools.exceptions import FileNotFoundError, NotAFileError, ToolError
from koda.tools.files import read_text_lines

if TYPE_CHECKING:
    from koda.tools.context import ToolContext


class ReadError(ToolError):
    """Failed to read file."""

    def __init__(self, path: str, *, cause: Exception) -> None:
        self.path = path
        self.cause = cause
        super().__init__(f"Failed to read '{path}': {cause}")


class ReadFileParams(BaseModel):
    """Parameters for reading a file."""

    path: str = Field(..., description="Path to the file to read")
    offset: int = Field(0, ge=0, description="Offset to start reading from")
    limit: int = Field(100, gt=0, description="Number of lines to read")


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
        target = AnyioPath(resolved)

        if not await target.exists():
            raise FileNotFoundError(params.path)

        if not await target.is_file():
            raise NotAFileError(params.path)

        decoded = await read_text_lines(
            resolved,
            params.path,
            offset=params.offset,
            limit=params.limit,
            error=ReadError,
        )
        text_content = decoded.text
        line_count = len(text_content.splitlines())
        noun = "line" if line_count == 1 else "lines"
        display = f"Read {line_count} {noun}"

        return ToolOutput(
            content={"text": text_content, "encoding": decoded.encoding},
            display=display,
        )
