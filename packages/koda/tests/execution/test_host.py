import asyncio
import shutil
from pathlib import Path
from typing import Any

import pytest

from koda.execution.host import HostCommandExecutor


class _FakeSettings:
    bash_execution_sandbox = "host"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed")
class TestHostCommandExecutor:
    @pytest.mark.asyncio
    async def test_run_returns_stdout_stderr_and_exit_code(self, tmp_path: Path) -> None:
        executor = HostCommandExecutor(_FakeSettings())

        result = await executor.run(
            command="printf 'hello'; printf 'oops' >&2; exit 3",
            cwd=str(tmp_path),
            sandbox_dir=str(tmp_path),
            timeout_seconds=5,
        )

        assert result.stdout == "hello"
        assert result.stderr == "oops"
        assert result.exit_code == 3
        assert result.cwd == str(tmp_path)

    @pytest.mark.asyncio
    async def test_run_uses_non_interactive_bash_flags_and_new_session(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        class _FakeProcess:
            pid = 123
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                return b"", b""

        captured: dict[str, Any] = {}

        async def _fake_create_subprocess_exec(*args: object, **kwargs: object) -> _FakeProcess:
            captured["args"] = args
            captured["kwargs"] = kwargs
            return _FakeProcess()

        monkeypatch.setattr("koda.execution.host._get_bash_path", lambda: "/bin/bash")
        monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

        executor = HostCommandExecutor(_FakeSettings())
        await executor.run(
            command="printf test",
            cwd=str(tmp_path),
            sandbox_dir=str(tmp_path),
            timeout_seconds=5,
        )

        assert captured["args"] == (
            "/bin/bash",
            "--noprofile",
            "--norc",
            "-c",
            "printf test",
        )
        assert captured["kwargs"]["cwd"] == str(tmp_path)
        assert captured["kwargs"]["start_new_session"] is True
