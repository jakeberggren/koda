"""Tests for tools/executor.py - ToolExecutor and call_id preservation."""

import asyncio
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, Field

from koda.harness.workspace import Workspace
from koda.messages import ToolCall, ToolMessage, ToolOutput
from koda.tools import ToolExecutor, ToolRegistry

from .conftest import CrashTool, ErrorTool, SimpleTool

if TYPE_CHECKING:
    from pathlib import Path


class LockingParams(BaseModel):
    """Parameters for a test tool that coordinates file access."""

    path: str = Field(..., description="Path to the logical file")
    delay: float = Field(default=0.01, description="Artificial delay while holding the lock")


class LockTrackingTool:
    """Test tool that records maximum concurrency per resolved path."""

    name = "lock_tracking_tool"
    description = "Records concurrent access while using the workspace locks"
    parameters_model = LockingParams

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self._active_by_path: dict[Path, int] = {}
        self.max_active_by_path: dict[Path, int] = {}

    async def execute(self, params: LockingParams) -> ToolOutput:
        resolved = self.workspace.resolve(params.path)

        async with self.workspace.locks.path(resolved):
            active = self._active_by_path.get(resolved, 0) + 1
            self._active_by_path[resolved] = active
            previous_max = self.max_active_by_path.get(resolved, 0)
            self.max_active_by_path[resolved] = max(previous_max, active)
            try:
                await asyncio.sleep(params.delay)
            finally:
                self._active_by_path[resolved] -= 1

        return ToolOutput(content={"path": params.path})


class CoordinatedParams(BaseModel):
    """Parameters for a test tool using the workspace locks."""

    label: str = Field(..., description="Human-readable label for event tracking")
    delay: float = Field(default=0.01, description="Artificial delay while holding the lock")


class SharedAccessTool:
    """Test tool that uses shared execution access."""

    name = "shared_access_tool"
    description = "Uses shared execution access"
    parameters_model = CoordinatedParams

    def __init__(self, workspace: Workspace, timeline: list[str] | None = None) -> None:
        self.workspace = workspace
        self.active = 0
        self.max_active = 0
        self.events: list[str] = []
        self.timeline = timeline if timeline is not None else []

    async def execute(self, params: CoordinatedParams) -> ToolOutput:
        async with self.workspace.locks.shared():
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.events.append(f"shared_enter:{params.label}")
            self.timeline.append(f"shared_enter:{params.label}")
            try:
                await asyncio.sleep(params.delay)
            finally:
                self.active -= 1
                self.events.append(f"shared_exit:{params.label}")
                self.timeline.append(f"shared_exit:{params.label}")

        return ToolOutput(content={"label": params.label})


class ExclusiveAccessTool:
    """Test tool that uses exclusive execution access."""

    name = "exclusive_access_tool"
    description = "Uses exclusive execution access"
    parameters_model = CoordinatedParams

    def __init__(
        self,
        workspace: Workspace,
        shared_tool: SharedAccessTool,
        timeline: list[str] | None = None,
    ) -> None:
        self.workspace = workspace
        self.shared_tool = shared_tool
        self.shared_active_on_entry: list[int] = []
        self.events: list[str] = []
        self.timeline = timeline if timeline is not None else []

    async def execute(self, params: CoordinatedParams) -> ToolOutput:
        async with self.workspace.locks.exclusive():
            self.shared_active_on_entry.append(self.shared_tool.active)
            self.events.append(f"exclusive_enter:{params.label}")
            self.timeline.append(f"exclusive_enter:{params.label}")
            await asyncio.sleep(params.delay)
            self.events.append(f"exclusive_exit:{params.label}")
            self.timeline.append(f"exclusive_exit:{params.label}")

        return ToolOutput(content={"label": params.label})


class TestExecuteCall:
    """Tests for single tool execution."""

    @pytest.mark.asyncio
    async def test_returns_correct_call_id(
        self,
    ) -> None:
        """Tool execution returns a ToolMessage with the correct call_id."""
        executor = ToolExecutor(ToolRegistry([SimpleTool()]))

        call = ToolCall(tool_name="simple_tool", arguments={"name": "World"}, call_id="call_123")

        result = await executor.execute_call(call)

        assert isinstance(result, ToolMessage)
        assert result.call_id == "call_123"
        assert result.output.is_error is False
        assert result.output.content["result"] == "Hello World"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(
        self,
    ) -> None:
        """Calling an unknown tool returns an error ToolMessage with correct call_id."""
        executor = ToolExecutor(ToolRegistry())

        call = ToolCall(tool_name="nonexistent", arguments={}, call_id="call_unknown")

        result = await executor.execute_call(call)

        assert result.call_id == "call_unknown"
        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "not found" in result.output.error_message.lower()

    @pytest.mark.asyncio
    async def test_invalid_params_returns_error(
        self,
    ) -> None:
        """Invalid parameters return error ToolResult with correct call_id."""
        executor = ToolExecutor(ToolRegistry([SimpleTool()]))

        call = ToolCall(
            tool_name="simple_tool",
            arguments={"invalid_field": "value"},  # Missing required 'name'
            call_id="call_invalid",
        )

        result = await executor.execute_call(call)

        assert result.call_id == "call_invalid"
        assert result.output.is_error is True
        assert result.output.error_message is not None

    @pytest.mark.asyncio
    async def test_tool_error_returns_error_result(
        self,
    ) -> None:
        """ToolError from tool execution returns an error ToolMessage."""
        executor = ToolExecutor(ToolRegistry([ErrorTool()]))

        call = ToolCall(tool_name="error_tool", arguments={"name": "test"}, call_id="call_error")

        result = await executor.execute_call(call)

        assert result.call_id == "call_error"
        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "Intentional error" in result.output.error_message

    @pytest.mark.asyncio
    async def test_unexpected_exception_propagates(
        self,
    ) -> None:
        """Non-ToolError exceptions propagate out of the executor."""
        executor = ToolExecutor(ToolRegistry([CrashTool()]))

        call = ToolCall(tool_name="crash_tool", arguments={"name": "boom"}, call_id="call_crash")

        with pytest.raises(ValueError, match="Unexpected failure"):
            await executor.execute_call(call)


class TestExecuteCalls:
    """Tests for parallel tool execution."""

    @staticmethod
    async def _collect_results(
        executor: ToolExecutor,
        calls: list[ToolCall],
    ) -> list[ToolMessage]:
        return [message async for message in executor.execute_calls(calls)]

    @pytest.mark.asyncio
    async def test_multiple_calls_preserve_call_ids(
        self,
    ) -> None:
        """Multiple tool calls each return their correct call_id."""
        executor = ToolExecutor(ToolRegistry([SimpleTool()]))

        calls = [
            ToolCall(tool_name="simple_tool", arguments={"name": "A"}, call_id="call_a"),
            ToolCall(tool_name="simple_tool", arguments={"name": "B"}, call_id="call_b"),
            ToolCall(tool_name="simple_tool", arguments={"name": "C"}, call_id="call_c"),
        ]

        results = await self._collect_results(executor, calls)

        assert len(results) == len(calls)
        call_ids = {r.call_id for r in results}
        assert call_ids == {"call_a", "call_b", "call_c"}

    @pytest.mark.asyncio
    async def test_parallel_execution(
        self,
    ) -> None:
        """Tool calls execute in parallel."""
        executor = ToolExecutor(ToolRegistry([SimpleTool()]))

        calls = [
            ToolCall(tool_name="simple_tool", arguments={"name": str(i)}, call_id=f"call_{i}")
            for i in range(10)
        ]

        results = await self._collect_results(executor, calls)

        assert len(results) == len(calls)
        call_ids = {result.call_id for result in results}
        assert call_ids == {f"call_{i}" for i in range(10)}
        for result in results:
            assert result.output.is_error is False

    @pytest.mark.asyncio
    async def test_parallel_calls_share_file_lock_for_same_path(
        self,
        workspace: Workspace,
    ) -> None:
        """Parallel calls to the same path are serialized by the path lock."""
        tool = LockTrackingTool(workspace)
        executor = ToolExecutor(ToolRegistry([tool]))

        calls = [
            ToolCall(
                tool_name="lock_tracking_tool",
                arguments={"path": "shared.txt", "delay": 0.02},
                call_id="call_a",
            ),
            ToolCall(
                tool_name="lock_tracking_tool",
                arguments={"path": "./shared.txt", "delay": 0.02},
                call_id="call_b",
            ),
        ]

        results = await self._collect_results(executor, calls)

        assert all(result.output.is_error is False for result in results)
        resolved = workspace.resolve("shared.txt")
        assert tool.max_active_by_path[resolved] == 1

    @pytest.mark.asyncio
    async def test_shared_file_tools_still_run_concurrently_while_shell_waits(
        self,
        workspace: Workspace,
    ) -> None:
        """Shared file tools can overlap while exclusive shell work waits for them."""
        timeline: list[str] = []
        shared_tool = SharedAccessTool(workspace, timeline)
        exclusive_tool = ExclusiveAccessTool(workspace, shared_tool, timeline)
        executor = ToolExecutor(ToolRegistry([shared_tool, exclusive_tool]))

        calls = [
            ToolCall(
                tool_name="shared_access_tool",
                arguments={"label": "file_a", "delay": 0.03},
                call_id="call_a",
            ),
            ToolCall(
                tool_name="shared_access_tool",
                arguments={"label": "file_b", "delay": 0.03},
                call_id="call_b",
            ),
            ToolCall(
                tool_name="exclusive_access_tool",
                arguments={"label": "bash", "delay": 0.01},
                call_id="call_shell",
            ),
        ]

        results = await self._collect_results(executor, calls)

        assert all(result.output.is_error is False for result in results)
        assert shared_tool.max_active == 2
        assert exclusive_tool.shared_active_on_entry == [0]

    @pytest.mark.asyncio
    async def test_waiting_shell_blocks_late_shared_arrivals(
        self,
        workspace: Workspace,
    ) -> None:
        """A queued exclusive shell call should prevent later shared work from jumping ahead."""
        timeline: list[str] = []
        shared_tool = SharedAccessTool(workspace, timeline)
        exclusive_tool = ExclusiveAccessTool(workspace, shared_tool, timeline)
        executor = ToolExecutor(ToolRegistry([shared_tool, exclusive_tool]))

        first_shared = asyncio.create_task(
            executor.execute_call(
                ToolCall(
                    tool_name="shared_access_tool",
                    arguments={"label": "first", "delay": 0.03},
                    call_id="call_first",
                ),
            ),
        )
        await asyncio.sleep(0.005)

        waiting_shell = asyncio.create_task(
            executor.execute_call(
                ToolCall(
                    tool_name="exclusive_access_tool",
                    arguments={"label": "bash", "delay": 0.01},
                    call_id="call_shell",
                ),
            ),
        )
        await asyncio.sleep(0.005)

        late_shared = asyncio.create_task(
            executor.execute_call(
                ToolCall(
                    tool_name="shared_access_tool",
                    arguments={"label": "late", "delay": 0.01},
                    call_id="call_late",
                ),
            ),
        )

        results = await asyncio.gather(first_shared, waiting_shell, late_shared)

        assert all(result.output.is_error is False for result in results)
        assert exclusive_tool.events == ["exclusive_enter:bash", "exclusive_exit:bash"]
        assert timeline == [
            "shared_enter:first",
            "shared_exit:first",
            "exclusive_enter:bash",
            "exclusive_exit:bash",
            "shared_enter:late",
            "shared_exit:late",
        ]

    @pytest.mark.asyncio
    async def test_mixed_success_and_error(
        self,
    ) -> None:
        """Mixed success and error results preserve correct call_ids."""
        executor = ToolExecutor(ToolRegistry([SimpleTool(), ErrorTool()]))

        calls = [
            ToolCall(tool_name="simple_tool", arguments={"name": "ok"}, call_id="call_ok"),
            ToolCall(tool_name="error_tool", arguments={"name": "fail"}, call_id="call_fail"),
        ]

        results = await self._collect_results(executor, calls)

        assert len(results) == len(calls)

        ok_result = next(r for r in results if r.call_id == "call_ok")
        fail_result = next(r for r in results if r.call_id == "call_fail")

        assert ok_result.output.is_error is False
        assert fail_result.output.is_error is True
