from __future__ import annotations

from typing import TYPE_CHECKING

from koda.llm.types import (
    LLMEvent,
    LLMResponseCompleted,
    LLMTextDelta,
    LLMThinkingDelta,
    LLMToolCallRequested,
    LLMToolCallResult,
    LLMToolCompleted,
    LLMToolStarted,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from koda.tools import ToolCall


class AgentStreamAccumulator:
    """Collect assistant output while passing stream events through."""

    def __init__(self) -> None:
        self.response_chunks: list[str] = []
        self.thinking_chunks: list[str] = []
        self.tool_calls: list[ToolCall] = []
        self.completed_response: LLMResponseCompleted | None = None

    @property
    def content(self) -> str:
        return "".join(self.response_chunks)

    @property
    def thinking_content(self) -> str:
        return "".join(self.thinking_chunks)

    def process_response_completed(self, event: LLMResponseCompleted) -> None:
        if not self.response_chunks and event.response.output.content:
            self.response_chunks.append(event.response.output.content)

        pending_call_ids = {call.call_id for call in self.tool_calls}
        for tool_call in event.response.output.tool_calls:
            if tool_call.call_id in pending_call_ids:
                continue
            self.tool_calls.append(tool_call)
            pending_call_ids.add(tool_call.call_id)

    def process_event(self, event: LLMEvent) -> list[LLMEvent]:  # noqa: C901 - allow complex
        if isinstance(event, LLMTextDelta):
            self.response_chunks.append(event.text)
            return [event]
        if isinstance(event, LLMThinkingDelta):
            self.thinking_chunks.append(event.text)
            return [event]
        if isinstance(event, LLMToolCallRequested):
            self.tool_calls.append(event.call)
            return [event]
        if isinstance(event, (LLMToolStarted, LLMToolCompleted, LLMToolCallResult)):
            return [event]
        if isinstance(event, LLMResponseCompleted):
            self.completed_response = event
            self.process_response_completed(event)
            return [event]
        return []

    async def process_stream(self, stream: AsyncIterator[LLMEvent]) -> AsyncIterator[LLMEvent]:
        async for event in stream:
            for processed_event in self.process_event(event):
                yield processed_event
