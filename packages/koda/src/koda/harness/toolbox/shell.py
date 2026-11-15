"""The shell tool: running a command with bash."""

from __future__ import annotations

import asyncio
import functools
import os
import shutil
import signal
from contextlib import suppress
from typing import TYPE_CHECKING

from anyio import Path as AnyioPath
from pydantic import BaseModel, Field

from koda.harness.workspace import NotAFolderError, PathNotFoundError
from koda.messages import ToolOutput
from koda.tools import ToolError

if TYPE_CHECKING:
    from pathlib import Path

    from koda.harness.workspace import Workspace


BASH_TIMEOUT_SECONDS = 30.0
BASH_MAX_OUTPUT_CHARS = 64_000


class BashNotFoundError(ToolError):
    """Bash binary not found on system."""

    def __init__(self) -> None:
        super().__init__("bash not found.")


class BashError(ToolError):
    """Error launching bash."""

    def __init__(self, cause: Exception) -> None:
        self.cause = cause
        super().__init__(f"Failed to execute bash: {cause}")


class BashTimeoutError(ToolError):
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


@functools.lru_cache(maxsize=1)
def bash_path() -> str:
    bash = shutil.which("bash")
    if bash is None:
        raise BashNotFoundError
    return bash


async def kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Best-effort kill of the command and anything it spawned."""
    if proc.returncode is not None:
        return
    try:
        # The command runs in its own session, so its pid is also its process group id.
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        with suppress(PermissionError, ProcessLookupError):
            proc.kill()
    with suppress(TimeoutError, ProcessLookupError):
        await asyncio.wait_for(proc.wait(), timeout=1)


async def run_bash(command: str, *, cwd: Path, timeout_seconds: float) -> tuple[str, str, int]:
    """Run ``command`` with bash in ``cwd`` on the host; return stdout, stderr, exit code."""
    try:
        proc = await asyncio.create_subprocess_exec(
            bash_path(),
            "--noprofile",
            "--norc",
            "-c",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            start_new_session=True,  # Own process group, so a timeout can kill its children too.
        )
    except OSError as e:
        raise BashError(e) from e

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except TimeoutError:
        await kill_process_tree(proc)
        raise BashTimeoutError(timeout_seconds) from None

    return (
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
        await proc.wait(),
    )


def truncate_output(value: str, *, max_chars: int = BASH_MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    if len(value) <= max_chars:
        return value, False
    marker = "\n\n... [truncated] ...\n\n"
    available = max_chars - len(marker)
    if available <= 0:
        return value[:max_chars], True

    head_chars = available // 4  # Keep more room for the tail, where failures usually appear.
    tail_chars = available - head_chars
    return f"{value[:head_chars]}{marker}{value[-tail_chars:]}", True


def build_output(
    *,
    params: BashParams,
    stdout: str,
    stderr: str,
    exit_code: int,
    cwd: str,
) -> ToolOutput:
    truncated_stdout, stdout_truncated = truncate_output(stdout)
    truncated_stderr, stderr_truncated = truncate_output(stderr)
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
        is_error=exit_code != 0,
    )


async def resolve_cwd(params: BashParams, workspace: Workspace) -> Path:
    resolved_cwd: Path = workspace.resolve(params.cwd)
    async_cwd = AnyioPath(resolved_cwd)

    if not await async_cwd.exists():
        raise PathNotFoundError(params.cwd)

    if not await async_cwd.is_dir():
        raise NotAFolderError(params.cwd)

    return resolved_cwd


class BashTool:
    """Execute a bash command on the host."""

    name: str = "bash"
    description: str = (
        "Execute a bash command on the host. Use this for shell-based "
        "inspection and development tasks such as running tests, linters, formatters, build "
        "commands, git commands, or searching the workspace with CLI tools. The working "
        "directory is the given cwd, relative to the workspace. Commands run "
        "with the user's permissions and can read and modify any file the user can. Returns "
        "stdout, stderr, "
        "exit_code, command, and cwd."
    )
    parameters_model: type[BashParams] = BashParams

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    async def execute(self, params: BashParams) -> ToolOutput:
        resolved_cwd = await resolve_cwd(params, self.workspace)

        async with self.workspace.coordinator.exclusive_access():
            stdout, stderr, exit_code = await run_bash(
                params.command,
                cwd=resolved_cwd,
                timeout_seconds=params.timeout_seconds,
            )

        return build_output(
            params=params,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            cwd=str(resolved_cwd),
        )
