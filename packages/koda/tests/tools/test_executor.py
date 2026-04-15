"""Tests for tools/executor.py - ToolExecutor and call_id preservation."""

import asyncio
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, Field

from koda.tools import ToolCall, ToolContext, ToolExecutor, ToolOutput, ToolRegistry, ToolResult

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
    description = "Records concurrent access while using the file coordinator"
    parameters_model = LockingParams

    def __init__(self) -> None:
        self._active_by_path: dict[Path, int] = {}
        self.max_active_by_path: dict[Path, int] = {}

    async def execute(self, params: LockingParams, ctx: ToolContext) -> ToolOutput:
        resolved = ctx.policy.resolve_path(params.path, cwd=ctx.cwd)

        async with ctx.files.lock_for(resolved):
            active = self._active_by_path.get(resolved, 0) + 1
            self._active_by_path[resolved] = active
            previous_max = self.max_active_by_path.get(resolved, 0)
            self.max_active_by_path[resolved] = max(previous_max, active)
            try:
                await asyncio.sleep(params.delay)
            finally:
                self._active_by_path[resolved] -= 1

        return ToolOutput(content={"path": params.path})


class TestExecuteCall:
    """Tests for single tool execution."""

    @pytest.mark.asyncio
    async def test_returns_correct_call_id(
        self, registry: ToolRegistry, context: ToolContext
    ) -> None:
        """Tool execution returns ToolResult with the correct call_id."""
        registry.register(SimpleTool())
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="simple_tool",
            arguments={"name": "World"},
            call_id="call_123",
        )

        result = await executor.execute_call(call, context)

        assert isinstance(result, ToolResult)
        assert result.call_id == "call_123"
        assert result.output.is_error is False
        assert result.output.content["result"] == "Hello World"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(
        self, registry: ToolRegistry, context: ToolContext
    ) -> None:
        """Calling an unknown tool returns error ToolResult with correct call_id."""
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="nonexistent",
            arguments={},
            call_id="call_unknown",
        )

        result = await executor.execute_call(call, context)

        assert result.call_id == "call_unknown"
        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "not found" in result.output.error_message.lower()

    @pytest.mark.asyncio
    async def test_invalid_params_returns_error(
        self, registry: ToolRegistry, context: ToolContext
    ) -> None:
        """Invalid parameters return error ToolResult with correct call_id."""
        registry.register(SimpleTool())
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="simple_tool",
            arguments={"invalid_field": "value"},  # Missing required 'name'
            call_id="call_invalid",
        )

        result = await executor.execute_call(call, context)

        assert result.call_id == "call_invalid"
        assert result.output.is_error is True
        assert result.output.error_message is not None

    @pytest.mark.asyncio
    async def test_tool_error_returns_error_result(
        self, registry: ToolRegistry, context: ToolContext
    ) -> None:
        """ToolError from tool execution returns error ToolResult."""
        registry.register(ErrorTool())
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="error_tool",
            arguments={"name": "test"},
            call_id="call_error",
        )

        result = await executor.execute_call(call, context)

        assert result.call_id == "call_error"
        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert "Intentional error" in result.output.error_message

    @pytest.mark.asyncio
    async def test_unexpected_exception_propagates(
        self, registry: ToolRegistry, context: ToolContext
    ) -> None:
        """Non-ToolError exceptions propagate out of the executor."""
        registry.register(CrashTool())
        executor = ToolExecutor(registry)

        call = ToolCall(
            tool_name="crash_tool",
            arguments={"name": "boom"},
            call_id="call_crash",
        )

        with pytest.raises(ValueError, match="Unexpected failure"):
            await executor.execute_call(call, context)


class TestExecuteCalls:
    """Tests for parallel tool execution."""

    @pytest.mark.asyncio
    async def test_multiple_calls_preserve_call_ids(
        self, registry: ToolRegistry, context: ToolContext
    ) -> None:
        """Multiple tool calls each return their correct call_id."""
        registry.register(SimpleTool())
        executor = ToolExecutor(registry)

        calls = [
            ToolCall(tool_name="simple_tool", arguments={"name": "A"}, call_id="call_a"),
            ToolCall(tool_name="simple_tool", arguments={"name": "B"}, call_id="call_b"),
            ToolCall(tool_name="simple_tool", arguments={"name": "C"}, call_id="call_c"),
        ]

        results = await executor.execute_calls(calls, context)

        assert len(results) == len(calls)
        call_ids = {r.call_id for r in results}
        assert call_ids == {"call_a", "call_b", "call_c"}

    @pytest.mark.asyncio
    async def test_parallel_execution(self, registry: ToolRegistry, context: ToolContext) -> None:
        """Tool calls execute in parallel via asyncio.gather."""
        registry.register(SimpleTool())
        executor = ToolExecutor(registry)

        calls = [
            ToolCall(tool_name="simple_tool", arguments={"name": str(i)}, call_id=f"call_{i}")
            for i in range(10)
        ]

        results = await executor.execute_calls(calls, context)

        assert len(results) == len(calls)
        for i, result in enumerate(results):
            assert result.call_id == f"call_{i}"
            assert result.output.is_error is False

    @pytest.mark.asyncio
    async def test_parallel_calls_share_file_lock_for_same_path(
        self, registry: ToolRegistry, context: ToolContext
    ) -> None:
        """Parallel calls to the same path are serialized by the file coordinator."""
        tool = LockTrackingTool()
        registry.register(tool)
        executor = ToolExecutor(registry)

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

        results = await executor.execute_calls(calls, context)

        assert all(result.output.is_error is False for result in results)
        resolved = context.policy.resolve_path("shared.txt", cwd=context.cwd)
        assert tool.max_active_by_path[resolved] == 1

    @pytest.mark.asyncio
    async def test_mixed_success_and_error(
        self, registry: ToolRegistry, context: ToolContext
    ) -> None:
        """Mixed success and error results preserve correct call_ids."""
        registry.register(SimpleTool())
        registry.register(ErrorTool())
        executor = ToolExecutor(registry)

        calls = [
            ToolCall(tool_name="simple_tool", arguments={"name": "ok"}, call_id="call_ok"),
            ToolCall(tool_name="error_tool", arguments={"name": "fail"}, call_id="call_fail"),
        ]

        results = await executor.execute_calls(calls, context)

        assert len(results) == len(calls)

        ok_result = next(r for r in results if r.call_id == "call_ok")
        fail_result = next(r for r in results if r.call_id == "call_fail")

        assert ok_result.output.is_error is False
        assert fail_result.output.is_error is True
