import asyncio
import os
import platform
import shlex
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from koda.execution.exceptions import CommandExecutionError
from koda.execution.seatbelt import SeatbeltCommandExecutor

if TYPE_CHECKING:
    from koda_common.settings import SettingsManager

_CONFIGD_RULE = '(allow mach-lookup (global-name "com.apple.SystemConfiguration.configd"))'


@lru_cache(maxsize=1)
def _sandbox_exec_usable() -> bool:
    sandbox_exec = shutil.which("sandbox-exec")
    if sandbox_exec is None:
        return False
    try:
        result = subprocess.run(  # noqa: S603
            [sandbox_exec, "-p", "(version 1) (allow default)", "/usr/bin/true"],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


class _FakeSettings:
    bash_execution_sandbox = "seatbelt"


@pytest.mark.skipif(platform.system() != "Darwin", reason="seatbelt is macOS-only")
class TestSeatbeltCommandExecutor:
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not _sandbox_exec_usable(),
        reason="sandbox-exec is unavailable or unusable in this environment",
    )
    async def test_run_returns_stdout_stderr_and_exit_code(self, tmp_path: Path) -> None:
        executor = SeatbeltCommandExecutor(cast("SettingsManager", _FakeSettings()))

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
    async def test_run_uses_sandbox_exec_and_non_interactive_bash_flags(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        class _FakeProcess:
            pid = 789
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                return b"", b""

        captured: dict[str, Any] = {}

        async def _fake_create_subprocess_exec(*args: object, **kwargs: object) -> _FakeProcess:
            captured["args"] = args
            captured["kwargs"] = kwargs
            return _FakeProcess()

        monkeypatch.setattr(
            "koda.execution.seatbelt._get_sandbox_exec_path",
            lambda: "/usr/bin/sandbox-exec",
        )
        monkeypatch.setattr("koda.execution.seatbelt.platform.system", lambda: "Darwin")
        monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

        executor = SeatbeltCommandExecutor(cast("SettingsManager", _FakeSettings()))
        await executor.run(
            command="printf test",
            cwd=str(tmp_path),
            sandbox_dir=str(tmp_path),
            timeout_seconds=5,
        )

        args = captured["args"]
        assert args[0] == "/usr/bin/sandbox-exec"
        assert args[1] == "-p"
        assert str(tmp_path) in captured["kwargs"]["cwd"]
        assert "--noprofile" in args
        assert "--norc" in args
        assert args[-2:] == ("-c", "printf test")
        assert captured["kwargs"]["start_new_session"] is True
        assert captured["kwargs"]["env"]["TMP"] == captured["kwargs"]["env"]["TMPDIR"]
        assert captured["kwargs"]["env"]["TEMP"] == captured["kwargs"]["env"]["TMPDIR"]
        assert captured["kwargs"]["env"]["HOME"] == captured["kwargs"]["env"]["TMPDIR"]
        assert captured["kwargs"]["env"]["XDG_CACHE_HOME"] == captured["kwargs"]["env"]["TMPDIR"]
        profile = args[2]
        assert "(deny network*)" in profile
        assert _CONFIGD_RULE in profile
        assert "(allow file-read*)" in profile
        assert f'(subpath "{tmp_path}")' in profile
        assert '(subpath "/tmp")' not in profile
        assert '(subpath "/private/tmp")' not in profile

    @pytest.mark.asyncio
    async def test_run_can_reuse_executor_instance(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        class _FakeProcess:
            pid = 789
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                return b"", b""

        call_count = 0

        async def _fake_create_subprocess_exec(*args: object, **kwargs: object) -> _FakeProcess:
            del args, kwargs
            nonlocal call_count
            call_count += 1
            return _FakeProcess()

        monkeypatch.setattr(
            "koda.execution.seatbelt._get_sandbox_exec_path",
            lambda: "/usr/bin/sandbox-exec",
        )
        monkeypatch.setattr("koda.execution.seatbelt.platform.system", lambda: "Darwin")
        monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

        executor = SeatbeltCommandExecutor(cast("SettingsManager", _FakeSettings()))

        await executor.run(
            command="printf first",
            cwd=str(tmp_path),
            sandbox_dir=str(tmp_path),
            timeout_seconds=5,
        )
        await executor.run(
            command="printf second",
            cwd=str(tmp_path),
            sandbox_dir=str(tmp_path),
            timeout_seconds=5,
        )

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_run_rejects_non_macos(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("koda.execution.seatbelt.platform.system", lambda: "Linux")
        executor = SeatbeltCommandExecutor(cast("SettingsManager", _FakeSettings()))
        with pytest.raises(CommandExecutionError, match="macOS"):
            await executor.run(
                command="printf test",
                cwd=str(tmp_path),
                sandbox_dir=str(tmp_path),
                timeout_seconds=5,
            )

    @pytest.mark.asyncio
    async def test_run_rejects_cwd_outside_sandbox(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("koda.execution.seatbelt.platform.system", lambda: "Darwin")
        executor = SeatbeltCommandExecutor(cast("SettingsManager", _FakeSettings()))
        outside = tmp_path.parent

        with pytest.raises(CommandExecutionError, match="within the sandbox directory"):
            await executor.run(
                command="printf test",
                cwd=str(outside),
                sandbox_dir=str(tmp_path),
                timeout_seconds=5,
            )

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not _sandbox_exec_usable(),
        reason="sandbox-exec is unavailable or unusable in this environment",
    )
    async def test_run_allows_workspace_and_outside_reads(self, tmp_path: Path) -> None:
        executor = SeatbeltCommandExecutor(cast("SettingsManager", _FakeSettings()))
        inside_file = tmp_path / "inside.txt"
        outside_file = tmp_path.parent / f"{tmp_path.name}-outside.txt"
        inside_file.write_text("inside\n")
        outside_file.write_text("outside\n")

        result = await executor.run(
            command=(f"cat {shlex.quote(str(inside_file))}; cat {shlex.quote(str(outside_file))}"),
            cwd=str(tmp_path),
            sandbox_dir=str(tmp_path),
            timeout_seconds=5,
        )

        assert result.stdout == "inside\noutside\n"
        assert result.stderr == ""
        assert result.exit_code == 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not _sandbox_exec_usable(),
        reason="sandbox-exec is unavailable or unusable in this environment",
    )
    async def test_run_allows_workspace_writes_and_blocks_outside_writes(
        self, tmp_path: Path
    ) -> None:
        executor = SeatbeltCommandExecutor(cast("SettingsManager", _FakeSettings()))
        outside_dir = tmp_path.parent / f"{tmp_path.name}-outside"
        outside_dir.mkdir()

        result = await executor.run(
            command=(
                f"touch {shlex.quote(str(tmp_path / 'inside.txt'))}; "
                f"touch {shlex.quote(str(outside_dir / 'outside.txt'))}"
            ),
            cwd=str(tmp_path),
            sandbox_dir=str(tmp_path),
            timeout_seconds=5,
        )

        assert (tmp_path / "inside.txt").exists()
        assert not (outside_dir / "outside.txt").exists()
        assert result.exit_code != 0
        assert "Operation not permitted" in result.stderr

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not _sandbox_exec_usable() or shutil.which("curl") is None,
        reason="sandbox-exec must be usable and curl installed",
    )
    async def test_run_blocks_network_access(self, tmp_path: Path) -> None:
        executor = SeatbeltCommandExecutor(cast("SettingsManager", _FakeSettings()))
        project_root = Path.cwd()

        result = await executor.run(
            command="curl -I https://example.com",
            cwd=str(project_root),
            sandbox_dir=str(project_root),
            timeout_seconds=30,
        )

        assert result.exit_code != 0
