from __future__ import annotations

import asyncio
import os
import signal
from contextlib import suppress


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
