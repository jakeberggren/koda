"""The glob tool: finding files by name."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from anyio import to_thread
from pydantic import BaseModel, Field

from koda.messages import ToolOutput

if TYPE_CHECKING:
    from koda.harness.workspace import Workspace


class GlobParams(BaseModel):
    """Parameters for globbing files."""

    pattern: str = Field(
        default="*",
        description="Glob pattern to match. Use * for single directory, ** for recursive.",
    )
    path: str = Field(
        default=".",
        description="Directory to search in. Defaults to current working directory.",
    )
    limit: int = Field(default=100, description="Maximum number of results to return.")


class GlobTool:
    """Tool for globbing files."""

    name: str = "glob"
    description: str = (
        "Find files matching a glob pattern. Supports recursive patterns with ** to search "
        "subdirectories (e.g., '**/*.py'). Returns relative paths sorted alphabetically, "
        "without files the workspace's .gitignore excludes or version-control folders. "
        "Use this to discover files by name pattern before reading them."
    )
    parameters_model: type[GlobParams] = GlobParams

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    async def execute(self, params: GlobParams) -> ToolOutput:
        folder = await self.workspace.folder(params.path)
        async with self.workspace.locks.shared():
            files = await to_thread.run_sync(self.workspace.files, folder)
        matches = [path for path in files if glob_match(path, params.pattern)]

        total_count: int = len(matches)
        truncated: bool = total_count > params.limit
        matches = matches[: params.limit]

        # Format output
        paths: list[str] = [str(p) for p in matches]
        paths_text: str = "\n".join(paths)

        if total_count == 0:
            display = f"No files found matching '{params.pattern}'"
            text = display
        else:
            shown = f" showing first {params.limit}" if truncated else ""
            noun = "file" if total_count == 1 else "files"
            display = f"Found {total_count} {noun} matching '{params.pattern}'{shown}"
            text = f"{display}:\n{paths_text}"

        return ToolOutput(content={"text": text}, display=display)


def glob_match(path: str, pattern: str) -> bool:
    """Whether the relative ``path`` matches the glob ``pattern``, where ``**`` matches any
    number of folders, none included."""
    return PurePosixPath(path).full_match(pattern)
