from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import ValidationError

from koda.tools import exceptions as tool_exceptions
from koda.tools.base import ToolCall, ToolOutput, ToolResult
from koda_common.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from koda.tools.context import ToolContext
    from koda.tools.registry import ToolRegistry


class ToolExecutor:
    """Executes tool calls using a ToolRegistry."""

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self.tool_registry = tool_registry

    async def execute_calls(self, tool_calls: list[ToolCall], ctx: ToolContext) -> list[ToolResult]:
        return await asyncio.gather(
            *[self.execute_call(call, ctx) for call in tool_calls],
        )

    async def execute_call(self, tool_call: ToolCall, ctx: ToolContext) -> ToolResult:
        tool = self.tool_registry.get(tool_call.tool_name)
        if not tool:
            logger.warning("tool_not_found", tool_name=tool_call.tool_name)
            return ToolResult(
                output=ToolOutput(
                    is_error=True,
                    error_message=f"Tool '{tool_call.tool_name}' not found",
                ),
                call_id=tool_call.call_id,
            )
        logger.info("executing_tool", tool_name=tool_call.tool_name, arguments=tool_call.arguments)
        try:
            params = tool.parameters_model.model_validate(tool_call.arguments)
        except ValidationError as e:
            logger.warning("tool_validation_error", tool_name=tool_call.tool_name, error=repr(e))
            return ToolResult(
                output=ToolOutput(is_error=True, error_message=str(e)),
                call_id=tool_call.call_id,
            )
        try:
            output = await tool.execute(params, ctx)
        except tool_exceptions.ToolError as e:
            logger.warning("tool_execution_error", tool_name=tool_call.tool_name, error=repr(e))
            return ToolResult(
                output=ToolOutput(is_error=True, error_message=str(e)),
                call_id=tool_call.call_id,
            )
        logger.info("tool_executed", tool_name=tool_call.tool_name, is_error=output.is_error)
        return ToolResult(output=output, call_id=tool_call.call_id)
