from __future__ import annotations

from difflib import unified_diff
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from koda.tools import ToolOutput, exceptions
from koda.tools.decorators import tool

if TYPE_CHECKING:
    from pathlib import Path

    from koda.tools.context import ToolContext


class EditError(exceptions.ToolError):
    """Failed to edit file."""

    def __init__(self, path: str, *, cause: Exception) -> None:
        self.path = path
        self.cause = cause
        super().__init__(f"Failed to edit '{path}': {cause}")


class TextNotFoundError(exceptions.ToolError):
    """Text to replace was not found in file."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Text not found in '{path}'")


class MultipleMatchesError(exceptions.ToolError):
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

    def _read_file(self, resolved: Path, path: str) -> str:
        """Read file content with error handling."""
        try:
            return resolved.read_text(encoding="utf-8")
        except PermissionError as e:
            raise exceptions.PermissionError(path) from e
        except OSError as e:
            raise EditError(path, cause=e) from e

    def _write_file(self, resolved: Path, path: str, content: str) -> None:
        """Write file content with error handling."""
        try:
            resolved.write_text(content, encoding="utf-8")
        except PermissionError as e:
            raise exceptions.PermissionError(path) from e
        except OSError as e:
            raise EditError(path, cause=e) from e

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
        resolved: Path = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)
        # Validate we are within the sandbox
        ctx.policy.resolve_path(str(resolved.parent), cwd=ctx.cwd)

        if not resolved.exists():
            raise exceptions.FileNotFoundError(params.path)
        if not resolved.is_file():
            raise exceptions.NotAFileError(params.path)

        original = self._read_file(resolved, params.path)
        updated, replacements_made = self._apply_replacement(original, params)

        if updated != original:
            self._write_file(resolved, params.path, updated)

        diff_text = self._build_diff(original, updated, params.path)

        return ToolOutput(
            content={
                "success": True,
                "path": params.path,
                "replacements": replacements_made,
                "diff": diff_text,
            },
            display=diff_text or "No changes",
        )
