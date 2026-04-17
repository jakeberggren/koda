from __future__ import annotations

import asyncio
import functools
import re
import shutil
from typing import TYPE_CHECKING

from anyio import Path as AnyioPath
from pydantic import BaseModel, Field

from koda.tools import ToolContext, ToolOutput, exceptions
from koda.tools.decorators import tool

if TYPE_CHECKING:
    from pathlib import Path

BASH_TIMEOUT_SECONDS = 30.0


class BashNotFoundError(exceptions.ToolError):
    """Bash binary not found on system."""

    def __init__(self) -> None:
        super().__init__("bash not found.")


class BashError(exceptions.ToolError):
    """Error launching bash."""

    def __init__(self, cause: Exception) -> None:
        self.cause = cause
        super().__init__(f"Failed to execute bash: {cause}")


class BashTimeoutError(exceptions.ToolError):
    """Bash execution timed out."""

    def __init__(self, timeout: float) -> None:
        super().__init__(f"bash timed out after {timeout} seconds")


class DangerousCommandError(exceptions.ToolError):
    """Command rejected by the bash safety preflight checks."""

    def __init__(self, command: str, *, reason: str) -> None:
        self.command = command
        self.reason = reason
        super().__init__(f"Command rejected by bash safety policy: {reason}")


class BashParams(BaseModel):
    """Parameters for executing a bash command."""

    command: str = Field(..., description="Bash command to execute")
    cwd: str = Field(default=".", description="Working directory for the command")
    timeout_seconds: float = Field(
        default=BASH_TIMEOUT_SECONDS,
        gt=0,
        le=300,
        description="Maximum execution time in seconds",
    )


DESTRUCTIVE_COMMAND_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(^|[;&|()]|\n)\s*rm\s+(-[^\n]*\s+)?[^\n]+", re.IGNORECASE),
        "destructive file deletion via 'rm' is not allowed",
    ),
    (
        re.compile(r"(^|[;&|()]|\n)\s*find\b[^\n]*\s-delete\b", re.IGNORECASE),
        "destructive deletion via 'find -delete' is not allowed",
    ),
    (
        re.compile(r"(^|[;&|()]|\n)\s*mkfs(?:\.[^\s]+)?\b", re.IGNORECASE),
        "filesystem formatting commands are not allowed",
    ),
    (
        re.compile(r"(^|[;&|()]|\n)\s*dd\b[^\n]*\bof=/dev/", re.IGNORECASE),
        "raw device writes via 'dd' are not allowed",
    ),
    (
        re.compile(r"(^|[;&|()]|\n)\s*(shutdown|reboot|halt|poweroff)\b", re.IGNORECASE),
        "system power-management commands are not allowed",
    ),
)


@functools.lru_cache(maxsize=1)
def _get_bash_path() -> str:
    """Get path to bash binary. Result is cached to avoid repeated lookups."""
    bash = shutil.which("bash")
    if bash is None:
        raise BashNotFoundError
    return bash


def _validate_command(command: str) -> None:
    """Reject obviously destructive shell commands.

    This is a best-effort guardrail, not a security boundary.
    """
    for pattern, reason in DESTRUCTIVE_COMMAND_PATTERNS:
        if pattern.search(command):
            raise DangerousCommandError(command, reason=reason)


@tool
class BashTool:
    """Execute a bash command in a trusted local environment."""

    name: str = "bash"
    description: str = (
        "Execute a bash command in a trusted local environment. Uses a sandbox-resolved "
        "working directory, but the shell process itself is not fully filesystem-sandboxed. "
        "Applies best-effort checks for obviously destructive commands. Returns stdout, "
        "stderr, and exit code."
    )
    parameters_model: type[BashParams] = BashParams

    async def execute(self, params: BashParams, ctx: ToolContext) -> ToolOutput:
        _validate_command(params.command)

        resolved_cwd: Path = ctx.policy.resolve_path(params.cwd, cwd=ctx.cwd)
        async_cwd = AnyioPath(resolved_cwd)

        if not await async_cwd.exists():
            raise exceptions.FileNotFoundError(params.cwd)

        if not await async_cwd.is_dir():
            raise exceptions.NotADirectoryError(params.cwd)

        try:
            proc = await asyncio.create_subprocess_exec(
                _get_bash_path(),
                "-lc",
                params.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(resolved_cwd),
            )
        except OSError as e:
            raise BashError(e) from e

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=params.timeout_seconds
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise BashTimeoutError(params.timeout_seconds) from None

        exit_code = proc.returncode if proc.returncode is not None else -1
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        display = f"Command exited with code {exit_code}"

        return ToolOutput(
            content={
                "stdout": stdout_text,
                "stderr": stderr_text,
                "exit_code": exit_code,
                "command": params.command,
                "cwd": str(resolved_cwd),
            },
            display=display,
        )
