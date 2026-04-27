from __future__ import annotations

import asyncio
import os
import signal
from contextlib import suppress
from pathlib import Path

from anyio import Path as AnyioPath

from koda.execution.exceptions import CommandExecutionError


def _kill_process_group(proc: asyncio.subprocess.Process) -> bool:
    """Try to kill the subprocess group, returning True on success."""
    if proc.pid is None:
        return False
    with suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)
        return True
    return False


def _kill_process(proc: asyncio.subprocess.Process) -> bool:
    """Try to kill the direct subprocess, returning True on success."""
    with suppress(PermissionError, ProcessLookupError):
        proc.kill()
        return True
    return False


async def terminate_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Best-effort termination of the subprocess and any children it spawned."""
    if proc.returncode is not None:
        return

    killed = _kill_process_group(proc) or _kill_process(proc)
    if not killed:
        return

    with suppress(TimeoutError, ProcessLookupError):
        await asyncio.wait_for(proc.wait(), timeout=1)


async def resolve_sandbox_paths(*, cwd: str, sandbox_dir: str) -> tuple[Path, Path]:
    """Resolve sandbox paths and ensure cwd stays within the sandbox root."""
    resolved_sandbox_dir = Path(await AnyioPath(sandbox_dir).resolve())
    resolved_cwd = Path(await AnyioPath(cwd).resolve())
    if not resolved_cwd.is_relative_to(resolved_sandbox_dir):
        raise CommandExecutionError(ValueError("sandbox cwd must be within the sandbox directory"))
    return resolved_sandbox_dir, resolved_cwd
