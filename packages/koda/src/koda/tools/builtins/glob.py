from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.tools import ToolContext, ToolOutput, exceptions
from koda.tools.decorators import tool

if TYPE_CHECKING:
    from pathlib import Path


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


@tool
class GlobTool:
    """Tool for globbing files."""

    name: str = "glob"
    description: str = (
        "Find files matching a glob pattern. Supports recursive patterns with ** to search "
        "subdirectories (e.g., '**/*.py'). Returns relative paths sorted alphabetically. "
        "Use this to discover files by name pattern before reading them."
    )
    parameters_model: type[GlobParams] = GlobParams

    async def execute(self, params: GlobParams, ctx: ToolContext) -> ToolOutput:
        resolved: Path = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)

        if not resolved.exists():
            raise exceptions.FileNotFoundError(params.path)

        if not resolved.is_dir():
            raise exceptions.NotADirectoryError(params.path)

        matches = sorted(
            path.relative_to(resolved) for path in resolved.glob(params.pattern) if path.is_file()
        )

        total_count: int = len(matches)
        truncated: bool = total_count > params.limit
        matches: list[Path] = matches[: params.limit]

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
