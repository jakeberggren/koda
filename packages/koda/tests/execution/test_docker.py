import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from koda.execution.docker import (
    DOCKER_WORKSPACE_DIR,
    DockerCommandExecutor,
    DockerNotFoundError,
)
from koda.execution.exceptions import CommandExecutionError

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager


class _FakeSettings:
    bash_execution_sandbox = "docker"
    bash_execution_docker_image = "sandbox:latest"


class TestDockerCommandExecutor:
    @pytest.mark.asyncio
    async def test_run_uses_hardened_docker_flags(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        class _FakeProcess:
            pid = 456
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                return b"", b""

        captured: dict[str, Any] = {}

        async def _fake_create_subprocess_exec(*args: object, **kwargs: object) -> _FakeProcess:
            captured["args"] = args
            captured["kwargs"] = kwargs
            return _FakeProcess()

        monkeypatch.setattr("koda.execution.docker._get_docker_path", lambda: "/usr/bin/docker")
        monkeypatch.setattr("koda.execution.docker.os.getuid", lambda: 1000)
        monkeypatch.setattr("koda.execution.docker.os.getgid", lambda: 1000)
        monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

        executor = DockerCommandExecutor(cast("SettingsManager", _FakeSettings()))
        await executor.run(
            command="printf test",
            cwd=str(tmp_path),
            sandbox_dir=str(tmp_path),
            timeout_seconds=10,
        )

        args = captured["args"]
        assert args[0] == "/usr/bin/docker"
        assert "--cap-drop" in args
        assert "all" in args
        assert "--security-opt" in args
        assert "no-new-privileges" in args
        assert "--user" in args
        assert "1000:1000" in args
        assert "--read-only" in args
        assert "--pids-limit" in args
        assert "512" in args
        assert "--tmpfs" in args
        assert "--entrypoint" in args
        assert "bash" in args
        assert "--noprofile" in args
        assert "--norc" in args
        assert f"{tmp_path}:{DOCKER_WORKSPACE_DIR}:rw" in args
        assert captured["kwargs"]["start_new_session"] is True

    @pytest.mark.asyncio
    async def test_run_rejects_cwd_outside_sandbox(self, tmp_path: Path) -> None:
        executor = DockerCommandExecutor(cast("SettingsManager", _FakeSettings()))

        with pytest.raises(CommandExecutionError, match="within the sandbox directory"):
            await executor.run(
                command="printf test",
                cwd=str(tmp_path.parent),
                sandbox_dir=str(tmp_path),
                timeout_seconds=10,
            )

    @pytest.mark.asyncio
    async def test_run_wraps_missing_docker_cli(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def _raise_missing_docker() -> str:
            raise DockerNotFoundError

        monkeypatch.setattr("koda.execution.docker._get_docker_path", _raise_missing_docker)

        executor = DockerCommandExecutor(cast("SettingsManager", _FakeSettings()))

        with pytest.raises(CommandExecutionError, match="docker not found") as exc_info:
            await executor.run(
                command="printf test",
                cwd=str(tmp_path),
                sandbox_dir=str(tmp_path),
                timeout_seconds=10,
            )

        assert isinstance(exc_info.value.cause, DockerNotFoundError)
