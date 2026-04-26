from __future__ import annotations

import asyncio
import functools
import os
import platform
import shutil
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from koda.execution.exceptions import CommandExecutionError, CommandTimeoutError
from koda.execution.models import ExecutionResult
from koda.execution.protocols import CommandExecutor
from koda.execution.utils import resolve_sandbox_paths, terminate_process_tree

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager


class SandboxExecNotFoundError(Exception):
    """sandbox-exec binary not found on system."""

    def __init__(self) -> None:
        super().__init__("sandbox-exec not found")


@functools.lru_cache(maxsize=1)
def _get_sandbox_exec_path() -> str:
    """Resolve sandbox-exec once per process and fail with a clear error."""
    sandbox_exec = shutil.which("sandbox-exec")
    if sandbox_exec is None:
        raise SandboxExecNotFoundError
    return sandbox_exec


def _escape_profile_path(path: str) -> str:
    """Escape a filesystem path for inclusion in the profile string."""
    return path.replace("\\", "\\\\").replace('"', '\\"')


def _subpath_rule_lines(*paths: Path) -> list[str]:
    """Build `(subpath "...")` rules, including resolved and `/private` variants."""
    _private_prefix = "/private"
    subpaths: set[str] = set()

    for path in paths:
        candidates = {str(path)}

        with suppress(OSError):
            candidates.add(str(path.resolve()))

        for candidate in candidates:
            subpaths.add(candidate)
            if candidate.startswith(f"{_private_prefix}/"):
                subpaths.add(candidate.removeprefix(_private_prefix))

    return [f'    (subpath "{_escape_profile_path(path)}")' for path in sorted(subpaths)]


class SeatbeltCommandExecutor(CommandExecutor):
    """Execute commands in a macOS sandbox with broad reads and scoped writes."""

    def __init__(self, settings: SettingsManager) -> None:
        self._settings = settings

    @staticmethod
    def _execution_env(temp_dir: Path) -> dict[str, str]:
        env = dict(os.environ)
        env["HOME"] = str(temp_dir)
        env["TEMP"] = str(temp_dir)
        env["TMP"] = str(temp_dir)
        env["TMPDIR"] = str(temp_dir)
        # Redirect XDG caches into the writable scratch directory so tools that
        # would normally write under ~/.cache keep working under seatbelt's
        # restricted write policy.
        env["XDG_CACHE_HOME"] = str(temp_dir)
        return env

    async def run(
        self,
        *,
        command: str,
        cwd: str,
        sandbox_dir: str,
        timeout_seconds: float,
    ) -> ExecutionResult:
        if platform.system() != "Darwin":
            raise CommandExecutionError(RuntimeError("seatbelt sandbox is only supported on macOS"))

        resolved_sandbox_dir, resolved_cwd = await resolve_sandbox_paths(
            cwd=cwd,
            sandbox_dir=sandbox_dir,
        )

        try:
            with tempfile.TemporaryDirectory(prefix="koda-seatbelt-") as temp_dir_name:
                # Give the sandbox one ephemeral writable area for temp files and caches.
                temp_dir = Path(temp_dir_name)
                profile = "\n".join(
                    [
                        "(version 1)",
                        '(import "system.sb")',
                        "(deny default)",
                        "(deny network*)",
                        "(allow process-fork)",
                        "(allow signal (target self))",
                        "(allow sysctl-read)",
                        # Allow macOS SystemConfiguration lookups for tool compatibility.
                        '(allow mach-lookup (global-name "com.apple.SystemConfiguration.configd"))',
                        "(allow file-read*)",
                        "(allow file-map-executable process-exec)",
                        # Restrict writes to the workspace and this run's scratch dir.
                        "(allow file-write*",
                        *_subpath_rule_lines(resolved_sandbox_dir, temp_dir),
                        ")",
                    ]
                )
                sandbox_exec_path = _get_sandbox_exec_path()
                bash_path = shutil.which("bash") or "bash"
                bash_args = ("--noprofile", "--norc", "-c", command)
                sandbox_args = ("-p", profile, bash_path, *bash_args)

                proc = await asyncio.create_subprocess_exec(
                    sandbox_exec_path,
                    *sandbox_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(resolved_cwd),
                    env=self._execution_env(temp_dir),
                    start_new_session=True,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=timeout_seconds,
                    )
                except TimeoutError:
                    await terminate_process_tree(proc)
                    raise CommandTimeoutError(timeout_seconds) from None
        except (SandboxExecNotFoundError, OSError) as e:
            raise CommandExecutionError(e) from e

        return ExecutionResult(
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            exit_code=proc.returncode if proc.returncode is not None else -1,
            cwd=str(resolved_cwd),
        )
