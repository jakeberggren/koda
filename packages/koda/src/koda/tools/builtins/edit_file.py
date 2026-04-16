from __future__ import annotations

from difflib import unified_diff
from typing import TYPE_CHECKING

from anyio import Path as AnyioPath
from pydantic import BaseModel, Field

from koda.tools import ToolOutput
from koda.tools.decorators import tool
from koda.tools.exceptions import FileNotFoundError, NotAFileError, ToolError
from koda.tools.files import read_text, write_text

if TYPE_CHECKING:
    from pathlib import Path

    from koda.tools.context import ToolContext


class EditError(ToolError):
    """Failed to edit file."""

    def __init__(self, path: str, *, cause: Exception) -> None:
        self.path = path
        self.cause = cause
        super().__init__(f"Failed to edit '{path}': {cause}")


class TextNotFoundError(ToolError):
    """Text to replace was not found in file."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Text not found in '{path}'")


class MultipleMatchesError(ToolError):
    """Text to replace matched more than once in file."""

    def __init__(self, path: str, occurrences: int) -> None:
        self.path = path
        self.occurrences = occurrences
        super().__init__(
            f"Text appears {occurrences} times in '{path}'. "
            "Provide more context or set replace_all=True to edit all occurrences."
        )


class EditFileParams(BaseModel):
    """Parameters for editing a file."""

    path: str = Field(..., description="Path to the file to edit")
    old_text: str = Field(..., description="Text to replace", min_length=1)
    new_text: str = Field(..., description="Replacement text")
    replace_all: bool = Field(default=False, description="Replace all occurrences")


@tool
class EditFileTool:
    """Tool for editing file contents."""

    name: str = "edit_file"
    description: str = (
        "Edit a file by replacing text. Use this tool to make focused edits to files."
    )
    parameters_model: type[EditFileParams] = EditFileParams

    def _apply_replacement(self, original: str, params: EditFileParams) -> tuple[str, int]:
        occurrences = original.count(params.old_text)
        if occurrences == 0:
            raise TextNotFoundError(params.path)
        if not params.replace_all and occurrences > 1:
            raise MultipleMatchesError(params.path, occurrences)

        replacements = occurrences if params.replace_all else 1
        updated = original.replace(params.old_text, params.new_text, replacements)
        replacements_made = 0 if updated == original else replacements
        return updated, replacements_made

    def _build_diff(self, original: str, updated: str, path: str) -> str:
        diff_lines = unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
        )
        return "".join(diff_lines)

    async def execute(self, params: EditFileParams, ctx: ToolContext) -> ToolOutput:
        """Execute the edit_file tool."""
        resolved_path: Path = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)
        # Validate we are within the sandbox
        ctx.policy.resolve_path(str(resolved_path.parent), cwd=ctx.cwd)
        target = AnyioPath(resolved_path)

        if not await target.exists():
            raise FileNotFoundError(params.path)
        if not await target.is_file():
            raise NotAFileError(params.path)

        async with ctx.files.lock_for(resolved_path):
            decoded = await read_text(resolved_path, params.path, error=EditError)
            updated, replacements_made = self._apply_replacement(decoded.text, params)

            if updated != decoded.text:
                await write_text(
                    resolved_path,
                    params.path,
                    updated,
                    error=EditError,
                    encoding=decoded.encoding,
                )

        diff_text = self._build_diff(decoded.text, updated, params.path)

        return ToolOutput(
            content={
                "success": True,
                "path": params.path,
                "replacements": replacements_made,
                "diff": diff_text,
            },
            display=diff_text or "No changes",
        )
