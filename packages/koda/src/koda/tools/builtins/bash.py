from __future__ import annotations

from typing import TYPE_CHECKING

from anyio import Path as AnyioPath
from pydantic import BaseModel, Field

from koda.execution.exceptions import CommandExecutionError, CommandTimeoutError
from koda.execution.host import BashNotFoundError as ExecutorBashNotFoundError
from koda.tools import ToolContext, ToolOutput, exceptions
from koda.tools.decorators import tool

if TYPE_CHECKING:
    from pathlib import Path

BASH_TIMEOUT_SECONDS = 30.0
BASH_MAX_OUTPUT_CHARS = 64_000


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


def _truncate_output(value: str, *, max_chars: int = BASH_MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    marker = "\n\n... [truncated] ...\n\n"
    available = max_chars - len(marker)
    if available <= 0:
        return value[:max_chars], True

    head_chars = available // 4  # Keep more room for the tail, where failures usually appear.
    tail_chars = available - head_chars
    return f"{value[:head_chars]}{marker}{value[-tail_chars:]}", True


def _build_output(
    *,
    params: BashParams,
    stdout: str,
    stderr: str,
    exit_code: int,
    cwd: str,
) -> ToolOutput:
    truncated_stdout, stdout_truncated = _truncate_output(stdout)
    truncated_stderr, stderr_truncated = _truncate_output(stderr)
    return ToolOutput(
        content={
            "stdout": truncated_stdout,
            "stderr": truncated_stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "exit_code": exit_code,
            "command": params.command,
            "cwd": cwd,
        },
        display=f"Command exited with code {exit_code}",
    )


async def _resolve_cwd(params: BashParams, ctx: ToolContext) -> Path:
    resolved_cwd: Path = ctx.policy.resolve_path(params.cwd, cwd=ctx.cwd)
    async_cwd = AnyioPath(resolved_cwd)

    if not await async_cwd.exists():
        raise exceptions.FileNotFoundError(params.cwd)

    if not await async_cwd.is_dir():
        raise exceptions.NotADirectoryError(params.cwd)

    return resolved_cwd


@tool
class BashTool:
    """Execute a bash command in a trusted local environment."""

    name: str = "bash"
    description: str = (
        "Execute a bash command in the local execution environment. Use this for shell-based "
        "inspection and development tasks such as running tests, linters, formatters, build "
        "commands, git commands, or searching the workspace with CLI tools. The working "
        "directory is resolved through the tool policy from the provided cwd. Commands may "
        "read and modify files available to the execution environment. Returns stdout, stderr, "
        "exit_code, command, and cwd."
    )
    parameters_model: type[BashParams] = BashParams

    async def execute(self, params: BashParams, ctx: ToolContext) -> ToolOutput:
        resolved_cwd = await _resolve_cwd(params, ctx)

        async with ctx.coordinator.exclusive_access():
            try:
                result = await ctx.executor.run(
                    command=params.command,
                    cwd=str(resolved_cwd),
                    sandbox_dir=str(ctx.sandbox_dir),
                    timeout_seconds=params.timeout_seconds,
                )
            except ExecutorBashNotFoundError:
                raise BashNotFoundError from None
            except CommandTimeoutError:
                raise BashTimeoutError(params.timeout_seconds) from None
            except CommandExecutionError as e:
                raise BashError(e.cause) from e

        return _build_output(
            params=params,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            cwd=result.cwd,
        )
