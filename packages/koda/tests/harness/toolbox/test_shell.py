"""Tests for the shell tool: bash."""

from __future__ import annotations

import asyncio
import shutil
from typing import TYPE_CHECKING, Any

import pytest

from koda import harness
from koda.harness.toolbox.shell import BASH_MAX_OUTPUT_CHARS
from koda.harness.workspace import Workspace
from koda.messages import ToolCall
from koda.tools import ToolExecutor, ToolRegistry

from .conftest import content_text

if TYPE_CHECKING:
    from pathlib import Path


class TestBashTool:
    """Integration tests for bash tool."""

    bash_required = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed")

    @bash_required
    @pytest.mark.asyncio
    async def test_bash_executes_command_successfully(self, workspace_dir: Path) -> None:
        """bash tool executes a command and captures stdout."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="bash",
            arguments={"command": "printf 'hello'"},
            call_id="call_bash",
        )

        result = await executor.execute_call(call)

        assert result.call_id == "call_bash"
        assert result.output.is_error is False
        assert content_text(result, "stdout") == "hello"
        assert content_text(result, "stderr") == ""
        assert result.output.content["exit_code"] == 0
        assert result.output.display == "Command exited with code 0"

    @bash_required
    @pytest.mark.asyncio
    async def test_bash_captures_stderr(self, workspace_dir: Path) -> None:
        """bash tool captures stderr output."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="bash",
            arguments={"command": "printf 'oops' >&2"},
            call_id="call_bash_stderr",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert content_text(result, "stdout") == ""
        assert content_text(result, "stderr") == "oops"
        assert result.output.content["exit_code"] == 0

    @bash_required
    @pytest.mark.asyncio
    async def test_bash_marks_nonzero_exit_as_tool_error(self, workspace_dir: Path) -> None:
        """bash tool marks a non-zero exit as a tool error, keeping its output."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(tool_name="bash", arguments={"command": "exit 7"}, call_id="call_bash_exit")

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.content["exit_code"] == 7
        assert result.output.display == "Command exited with code 7"

    @bash_required
    @pytest.mark.asyncio
    async def test_bash_respects_cwd(self, workspace_dir: Path) -> None:
        """bash tool executes within the requested working directory."""
        nested = workspace_dir / "nested"
        nested.mkdir()

        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="bash",
            arguments={"command": "pwd", "cwd": "nested"},
            call_id="call_bash_cwd",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert content_text(result, "stdout").strip() == str(nested)
        assert content_text(result, "cwd") == str(nested)

    @pytest.mark.asyncio
    async def test_bash_cwd_not_found(self, workspace_dir: Path) -> None:
        """bash tool errors when cwd does not exist."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="bash",
            arguments={"command": "pwd", "cwd": "missing"},
            call_id="call_bash_missing",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "missing" in result.output.error_message

    @bash_required
    @pytest.mark.asyncio
    async def test_bash_timeout_returns_tool_error(self, workspace_dir: Path) -> None:
        """bash tool returns a tool error when execution times out."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        call = ToolCall(
            tool_name="bash",
            arguments={"command": "sleep 5", "timeout_seconds": 0.1},
            call_id="call_bash_timeout",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "timed out" in result.output.error_message

    @bash_required
    @pytest.mark.asyncio
    async def test_bash_timeout_kills_child_processes(self, workspace_dir: Path) -> None:
        """A timed-out command takes the processes it started down with it."""
        registry = ToolRegistry(harness.tools(Workspace(workspace_dir)))
        marker = workspace_dir / "survived"
        call = ToolCall(
            tool_name="bash",
            arguments={"command": f"(sleep 0.5; touch {marker}) & wait", "timeout_seconds": 0.1},
            call_id="call_bash_timeout_children",
        )

        result = await ToolExecutor(registry).execute_call(call)
        await asyncio.sleep(1)

        assert result.output.is_error is True
        assert not marker.exists()

    @pytest.mark.asyncio
    async def test_bash_runs_non_interactive_in_its_own_session(
        self,
        monkeypatch: pytest.MonkeyPatch,
        workspace_dir: Path,
    ) -> None:
        """bash skips profile/rc files and gets its own process group."""

        class _FakeProcess:
            pid = 123
            returncode = 0

            async def communicate(self) -> tuple[bytes, bytes]:
                return b"", b""

            async def wait(self) -> int:
                return 0

        captured: dict[str, Any] = {}

        async def _fake_create_subprocess_exec(*args: object, **kwargs: object) -> _FakeProcess:
            captured["args"] = args
            captured["kwargs"] = kwargs
            return _FakeProcess()

        monkeypatch.setattr("koda.harness.toolbox.shell.bash_path", lambda: "/bin/bash")
        monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
        registry = ToolRegistry(harness.tools(Workspace(workspace_dir)))
        call = ToolCall(
            tool_name="bash",
            arguments={"command": "printf test"},
            call_id="call_bash_flags",
        )

        await ToolExecutor(registry).execute_call(call)

        assert captured["args"] == ("/bin/bash", "--noprofile", "--norc", "-c", "printf test")
        assert captured["kwargs"]["cwd"] == workspace_dir
        assert captured["kwargs"]["start_new_session"] is True

    @bash_required
    @pytest.mark.asyncio
    async def test_bash_truncates_large_stdout_and_marks_it(self, workspace_dir: Path) -> None:
        """bash tool should truncate large stdout persisted in tool output."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        oversized = BASH_MAX_OUTPUT_CHARS + 100
        call = ToolCall(
            tool_name="bash",
            arguments={"command": f"python -c \"print('x' * {oversized}, end='')\""},
            call_id="call_bash_large_stdout",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert len(content_text(result, "stdout")) == BASH_MAX_OUTPUT_CHARS
        assert result.output.content["stdout_truncated"] is True
        assert result.output.content["stderr_truncated"] is False

    @bash_required
    @pytest.mark.asyncio
    async def test_bash_truncates_large_stderr_and_marks_it(self, workspace_dir: Path) -> None:
        """bash tool should truncate large stderr persisted in tool output."""
        executor = ToolExecutor(ToolRegistry(harness.tools(Workspace(workspace_dir))))

        oversized = BASH_MAX_OUTPUT_CHARS + 100
        call = ToolCall(
            tool_name="bash",
            arguments={"command": f"python -c \"import sys; sys.stderr.write('y' * {oversized})\""},
            call_id="call_bash_large_stderr",
        )

        result = await executor.execute_call(call)

        assert result.output.is_error is False
        assert len(content_text(result, "stderr")) == BASH_MAX_OUTPUT_CHARS
        assert result.output.content["stderr_truncated"] is True
        assert result.output.content["stdout_truncated"] is False
