from __future__ import annotations

import asyncio
import functools
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from koda.execution.exceptions import CommandExecutionError, CommandTimeoutError
from koda.execution.models import ExecutionResult
from koda.execution.protocols import CommandExecutor
from koda.execution.utils import resolve_sandbox_paths, terminate_process_tree

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager

DOCKER_WORKSPACE_DIR = "/workspace"


class DockerNotFoundError(Exception):
    """Docker CLI not found on system."""

    def __init__(self) -> None:
        super().__init__("docker not found")


@functools.lru_cache(maxsize=1)
def _get_docker_path() -> str:
    docker = shutil.which("docker")
    if docker is None:
        raise DockerNotFoundError
    return docker


def _container_cwd(*, cwd: Path, sandbox_dir: Path) -> str:
    relative = cwd.relative_to(sandbox_dir)
    if str(relative) == ".":
        return DOCKER_WORKSPACE_DIR
    return f"{DOCKER_WORKSPACE_DIR}/{relative.as_posix()}"


class DockerCommandExecutor(CommandExecutor):
    """Execute commands inside a short-lived docker container."""

    def __init__(self, settings: SettingsManager) -> None:
        self._settings = settings

    async def run(
        self,
        *,
        command: str,
        cwd: str,
        sandbox_dir: str,
        timeout_seconds: float,
    ) -> ExecutionResult:
        image = self._settings.bash_execution_docker_image
        if image is None:
            raise CommandExecutionError(ValueError("bash_execution_docker_image is not configured"))
        resolved_sandbox_dir, resolved_cwd = await resolve_sandbox_paths(
            cwd=cwd,
            sandbox_dir=sandbox_dir,
        )
        host_sandbox_dir = str(resolved_sandbox_dir)
        container_cwd = _container_cwd(cwd=resolved_cwd, sandbox_dir=resolved_sandbox_dir)
        uid = os.getuid()
        gid = os.getgid()
        docker_run_args = (
            "run",
            "--rm",  # Remove the container after the command exits.
            "--cap-drop",  # Drop Linux capabilities we do not explicitly need.
            "all",
            "--security-opt",  # Prevent setuid/setcap style privilege escalation.
            "no-new-privileges",
            "--user",  # Match host ownership for files written into the mounted workspace.
            f"{uid}:{gid}",
            "--read-only",  # Keep the image filesystem immutable during execution.
            "--pids-limit",  # Limit the number of processes the command can spawn.
            "512",
            "--tmpfs",  # Provide writable temporary space without making the image writable.
            "/tmp:rw,nosuid,nodev,noexec",  # noqa: S108 - Docker tmpfs mount, not host temp-file usage.
            "--tmpfs",  # Some tools also expect /var/tmp to be writable.
            "/var/tmp:rw,nosuid,nodev,noexec",  # noqa: S108 - Docker tmpfs mount, not host temp-file usage.
            "--env",  # Point HOME at a writable temp directory inside the container.
            "HOME=/tmp",
            "-v",  # Expose only the sandbox workspace as writable host state.
            f"{host_sandbox_dir}:{DOCKER_WORKSPACE_DIR}:rw",
            "-w",  # Start the command in the resolved workspace subdirectory.
            container_cwd,
            "--entrypoint",  # Force a predictable shell entrypoint regardless of image defaults.  # noqa: E501
            "bash",
            image,
            "--noprofile",  # Skip image-provided profile files for deterministic execution.
            "--norc",  # Skip shell rc files such as /etc/bash.bashrc and ~/.bashrc.
            "-c",  # Execute the provided command string.
            command,
        )

        try:
            docker_path = _get_docker_path()
            proc = await asyncio.create_subprocess_exec(
                docker_path,
                *docker_run_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path.cwd(),
                start_new_session=True,  # Create a new process group for timeout cleanup.
            )
        except DockerNotFoundError as e:
            raise CommandExecutionError(e) from e
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
