from __future__ import annotations

from typing import TYPE_CHECKING

from anyio import Path as AnyioPath
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
        directory = AnyioPath(resolved)

        if not await directory.exists():
            raise exceptions.FileNotFoundError(params.path)

        if not await directory.is_dir():
            raise exceptions.NotADirectoryError(params.path)

        try:
            dir_items = [item async for item in directory.iterdir()]
        except PermissionError as e:
            raise exceptions.PermissionError(params.path) from e
        except OSError as e:
            raise ListDirectoryError(params.path, cause=e) from e

        items = [
            {
                "name": item.name,
                "type": "directory" if await item.is_dir() else "file",
                "path": str(item),
            }
            for item in dir_items
        ]

        dir_count = sum(1 for i in items if i["type"] == "directory")
        file_count = len(items) - dir_count
        noun = "file" if file_count == 1 else "files"
        display = f"Listed {file_count} {noun}, {dir_count} directories"

        return ToolOutput(content={"items": items}, display=display)
