"""The read_file tool: a window of lines from a text file."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.harness.toolbox.files.content import read_text_lines
from koda.messages import ToolOutput

if TYPE_CHECKING:
    from koda.harness.workspace import Workspace


class ReadFileParams(BaseModel):
    """Parameters for reading a file."""

    path: str = Field(..., description="Path to the file to read")
    offset: int = Field(0, ge=0, description="Offset to start reading from")
    limit: int = Field(100, gt=0, description="Number of lines to read")


class ReadFileTool:
    """Tool for reading file contents."""

    name: str = "read_file"
    description: str = (
        "Read file contents (line-based). "
        "Prefer small ranges via offset/limit and expand as needed."
    )
    parameters_model: type[ReadFileParams] = ReadFileParams

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    async def execute(self, params: ReadFileParams) -> ToolOutput:
        """Execute the read_file tool."""
        resolved = await self.workspace.file(params.path)
        async with self.workspace.locks.shared():
            decoded = await read_text_lines(
                resolved,
                params.path,
                offset=params.offset,
                limit=params.limit,
            )
        text_content = decoded.text
        line_count = len(text_content.splitlines())
        noun = "line" if line_count == 1 else "lines"
        display = f"Read {line_count} {noun}"

        return ToolOutput(
            content={"text": text_content, "encoding": decoded.encoding},
            display=display,
        )
