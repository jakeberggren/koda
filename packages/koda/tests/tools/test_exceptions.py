"""Tests for tools/exceptions.py - error formatting."""

import pytest

from koda.messages import ToolCall
from koda.tools import ToolExecutor, ToolRegistry

from .conftest import ErrorTool


class TestErrorResultFormat:
    """Tests for error result formatting in execution."""

    @pytest.mark.asyncio
    async def test_error_result_structure(
        self,
    ) -> None:
        """Error results from execution have correct structure."""
        executor = ToolExecutor(ToolRegistry([ErrorTool()]))

        call = ToolCall(tool_name="error_tool", arguments={"name": "test"}, call_id="call_123")

        result = await executor.execute_call(call)

        assert result.output.is_error is True
        assert result.output.error_message is not None
        assert len(result.output.error_message) > 0
        assert result.output.content == {}  # Empty content on error
