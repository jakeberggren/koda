from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.tools import ToolOutput, exceptions
from koda.tools.decorators import tool

if TYPE_CHECKING:
    from koda.tools.context import ToolContext


class ListDirectoryError(exceptions.ToolError):
    """Failed to list directory."""

    def __init__(self, path: str, *, cause: Exception) -> None:
        self.path = path
        self.cause = cause
        super().__init__(f"Failed to list '{path}': {cause}")


class ListDirectoryParams(BaseModel):
    """Parameters for listing a directory."""

    path: str = Field(default=".", description="Path to the directory to list")


@tool
class ListDirectoryTool:
    """Tool for listing directory contents."""

    name: str = "list_directory"
    description: str = "List the contents of a directory"
    parameters_model: type[ListDirectoryParams] = ListDirectoryParams

    async def execute(self, params: ListDirectoryParams, ctx: ToolContext) -> ToolOutput:
        """Execute the list_directory tool."""
        resolved = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)

        if not resolved.exists():
            raise exceptions.FileNotFoundError(params.path)

        if not resolved.is_dir():
            raise exceptions.NotADirectoryError(params.path)

        try:
            dir_items = list(resolved.iterdir())
        except PermissionError as e:
            raise exceptions.PermissionError(params.path) from e
        except OSError as e:
            raise ListDirectoryError(params.path, cause=e) from e

        items = [
            {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "path": str(item),
            }
            for item in dir_items
        ]
        return ToolOutput(content={"items": items})
