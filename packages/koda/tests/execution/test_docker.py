import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from koda.execution.docker import DOCKER_WORKSPACE_DIR, DockerCommandExecutor, DockerSettings


class _FakeSettings:
    bash_execution_sandbox = "docker"
    bash_execution_docker_image = "bash:5.2"


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

        executor = DockerCommandExecutor(cast("DockerSettings", _FakeSettings()))
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
