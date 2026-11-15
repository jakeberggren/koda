from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import ValidationError

from koda.messages import ToolCall, ToolMessage, ToolOutput
from koda.tools.exceptions import ToolError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.tools.registry import ToolRegistry


class ToolExecutor:
    """Runs the model's tool calls with the tools in ``registry``."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def execute_call(self, call: ToolCall) -> ToolMessage:
        """Run ``call``. What the model can fix (an unknown tool, bad arguments, a ToolError)
        is answered as an error for it."""
        return answer(call, await self._run(call))

    async def execute_calls(self, calls: list[ToolCall]) -> AsyncIterator[ToolMessage]:
        """Run ``calls`` at the same time; each answer comes as soon as it is ready."""
        pending = {asyncio.create_task(self.execute_call(call)) for call in calls}

        try:
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    yield task.result()
        finally:
            for task in pending:
                task.cancel()

    async def _run(self, call: ToolCall) -> ToolOutput:
        tool = self.registry.get(call.tool_name)
        if tool is None:
            return ToolOutput.failure(f"Tool '{call.tool_name}' not found")
        try:
            params = tool.parameters_model.model_validate(call.arguments)
        except ValidationError as error:
            return ToolOutput.failure(str(error))
        try:
            return await tool.execute(params)
        except ToolError as error:
            return ToolOutput.failure(str(error))


def answer(call: ToolCall, output: ToolOutput) -> ToolMessage:
    """``output`` as the answer to ``call``."""
    return ToolMessage(tool_name=call.tool_name, call_id=call.call_id, output=output)
