from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.harness.toolbox.exceptions import ToolError
from koda.harness.toolbox.files import write_text
from koda.messages import ToolOutput

if TYPE_CHECKING:
    from pathlib import Path

    from koda.harness.toolbox.workspace import Workspace


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


class WriteFileTool:
    """Tool for writing file contents."""

    name: str = "write_file"
    description: str = (
        "Write content to a file on the filesystem."
        "Only use this tool to create new files."
        "To edit existing files, use the edit_file tool."
    )
    parameters_model: type[WriteFileParams] = WriteFileParams

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    async def execute(self, params: WriteFileParams) -> ToolOutput:
        """Execute the write_file tool."""
        resolved: Path = self.workspace.resolve(params.path)

        # Validate parent directory is also within sandbox

        async with (
            self.workspace.coordinator.shared_access(),
            self.workspace.coordinator.path_lock(resolved),
        ):
            await write_text(resolved, params.path, params.content, error=WriteError)

        line_count = params.content.count("\n") + (
            1 if params.content and not params.content.endswith("\n") else 0
        )
        noun = "line" if line_count == 1 else "lines"
        display = f"Wrote {line_count} {noun}"

        return ToolOutput(content={"success": True, "path": params.path}, display=display)
