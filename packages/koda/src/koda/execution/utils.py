from __future__ import annotations

import os
import signal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio


async def terminate_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Best-effort termination of the subprocess and any children it spawned."""
    if proc.returncode is not None:
        return
    try:
        if proc.pid is not None:
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except ProcessLookupError:
        pass
    await proc.wait()
