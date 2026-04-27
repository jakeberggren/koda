from __future__ import annotations

import asyncio
import functools
import shutil
from typing import TYPE_CHECKING

from koda.execution.exceptions import CommandExecutionError, CommandTimeoutError
from koda.execution.models import ExecutionResult
from koda.execution.protocols import CommandExecutor
from koda.execution.utils import terminate_process_tree

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager


class BashNotFoundError(Exception):
    """Bash binary not found on system."""

    def __init__(self) -> None:
        super().__init__("bash not found")


@functools.lru_cache(maxsize=1)
def _get_bash_path() -> str:
    bash = shutil.which("bash")
    if bash is None:
        raise BashNotFoundError
    return bash


class HostCommandExecutor(CommandExecutor):
    """Execute commands directly on the host using bash."""

    def __init__(self, settings: SettingsManager) -> None:
        self._settings = settings

    async def run(
        self,
        *,
        command: str,
        cwd: str,
        sandbox_dir: str,  # noqa: ARG002
        timeout_seconds: float,
    ) -> ExecutionResult:
        try:
            bash_path = _get_bash_path()
            bash_args = ("--noprofile", "--norc", "-c", command)
            proc = await asyncio.create_subprocess_exec(
                bash_path,
                *bash_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                start_new_session=True,  # Create a new process group for timeout cleanup.
            )
        except OSError as e:
            raise CommandExecutionError(e) from e

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            await terminate_process_tree(proc)
            raise CommandTimeoutError(timeout_seconds) from None

        return ExecutionResult(
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            exit_code=proc.returncode if proc.returncode is not None else -1,
            cwd=cwd,
        )
