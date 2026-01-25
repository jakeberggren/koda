from __future__ import annotations

import asyncio
import functools
import json
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from koda.tools import ToolContext, ToolOutput, exceptions
from koda.tools.decorators import tool

RIPGREP_TIMEOUT_SECONDS = 30.0


class RipgrepNotFoundError(exceptions.ToolError):
    """Ripgrep binary not found on system."""

    def __init__(self) -> None:
        super().__init__("ripgrep (rg) not found.")


class RipgrepError(exceptions.ToolError):
    """Error executing ripgrep."""

    def __init__(self, error_output: str, returncode: int) -> None:
        self.returncode = returncode
        self.error_output = error_output
        super().__init__(f"ripgrep failed (exit {returncode}): {error_output}")


class RipgrepTimeoutError(exceptions.ToolError):
    """Ripgrep execution timed out."""

    def __init__(self, timeout: float) -> None:
        super().__init__(f"ripgrep timed out after {timeout} seconds")


class GrepParams(BaseModel):
    """Parameters for grep search."""

    pattern: str = Field(..., description="Regex pattern to search for")
    path: str = Field(
        default=".",
        description="Directory or file to search in. Defaults to current working directory.",
    )
    glob: str | None = Field(
        default=None,
        description="Glob pattern to filter files (e.g., '*.py', '*.{ts,tsx}').",
    )
    file_type: str | None = Field(
        default=None,
        description="File type to search (e.g., 'py', 'js', 'rust').",
    )
    case_sensitive: bool = Field(
        default=True,
        description="Whether the search should be case-sensitive.",
    )
    limit: int = Field(
        default=100,
        description="Maximum number of matches to return.",
    )


@functools.lru_cache(maxsize=1)
def _get_rg_path() -> str:
    """Get path to ripgrep binary. Result is cached to avoid repeated lookups."""
    rg = shutil.which("rg")
    if rg is None:
        raise RipgrepNotFoundError
    return rg


def _build_rg_command(rg_path: str, params: GrepParams, target: Path) -> list[str]:
    """Build ripgrep command arguments."""
    cmd = [rg_path, "--json"]

    if not params.case_sensitive:
        cmd.append("--ignore-case")

    if params.glob:
        cmd.extend(["--glob", params.glob])

    if params.file_type:
        cmd.extend(["--type", params.file_type])

    cmd.extend(["-e", params.pattern, str(target)])
    return cmd


def _parse_rg_match(data: dict, search_root: Path) -> str | None:
    """Parse a single ripgrep JSON match entry."""
    if data.get("type") != "match":
        return None

    match_data = data["data"]
    path_text = match_data["path"]["text"]
    line_number = match_data["line_number"]
    line_text = match_data["lines"]["text"].rstrip("\n")

    base_path = search_root.parent if search_root.is_file() else search_root

    try:
        rel_path = Path(path_text).relative_to(base_path)
    except ValueError:
        rel_path = Path(path_text)

    return f"{rel_path}:{line_number}:{line_text}"


def _parse_json_line(line: str) -> dict | None:
    """Parse a JSON line, returning None if invalid."""
    if not line.strip():
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _parse_rg_output(stdout: bytes, search_root: Path, limit: int) -> tuple[list[str], int]:
    """Parse ripgrep JSON output and return matches with total count."""
    matches: list[str] = []
    total_count = 0

    for line in stdout.decode("utf-8", errors="replace").splitlines():
        data = _parse_json_line(line)
        if data is None:
            continue
        match_str = _parse_rg_match(data, search_root)
        if match_str is not None:
            total_count += 1
            if total_count <= limit:
                matches.append(match_str)

    return matches, total_count


def _format_grep_output(
    pattern: str, matches: list[str], total_count: int, limit: int
) -> tuple[str, str]:
    """Format grep results into display and text output."""
    if total_count == 0:
        display = f"No matches found for '{pattern}'"
        return display, display

    matches_text = "\n".join(matches)

    shown = f" (showing first {limit})" if total_count > limit else ""
    noun = "match" if total_count == 1 else "matches"
    display = f"Found {total_count} {noun} for '{pattern}'{shown}"

    return display, f"{display}:\n{matches_text}"


@tool
class GrepTool:
    """Fast file content search using ripgrep."""

    name: str = "grep"
    description: str = (
        "Search for text patterns in files using ripgrep. Fast recursive search with "
        "regex support, glob filtering, and file type selection. Returns matching lines "
        "with file names and line numbers."
    )
    parameters_model: type[GrepParams] = GrepParams

    async def execute(self, params: GrepParams, ctx: ToolContext) -> ToolOutput:
        resolved: Path = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)

        if not resolved.exists():
            raise exceptions.FileNotFoundError(params.path)

        cmd = _build_rg_command(_get_rg_path(), params, resolved)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(ctx.cwd),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=RIPGREP_TIMEOUT_SECONDS
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise RipgrepTimeoutError(RIPGREP_TIMEOUT_SECONDS) from None

        # returncode 0 = matches found, 1 = no matches, other = error
        returncode = proc.returncode
        if returncode is None:
            raise RipgrepError("incomplete", -1)
        if returncode not in (0, 1):
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            raise RipgrepError(error_msg, returncode)

        matches, total_count = _parse_rg_output(stdout, resolved, params.limit)
        display, text = _format_grep_output(params.pattern, matches, total_count, params.limit)

        return ToolOutput(content={"text": text}, display=display)
