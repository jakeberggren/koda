from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat.chat_completion_system_message_param import (
    ChatCompletionSystemMessageParam,
)

from koda.providers import Provider, exceptions, utils
from koda.providers.berget.adapter import BergetAIAdapter
from koda.providers.events import ProviderEvent, TextDelta, ToolCallRequested
from koda.tools import ToolCall, ToolDefinition
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from openai.types.chat.chat_completion_chunk import (
        ChatCompletionChunk,
        Choice,
        ChoiceDeltaToolCall,
    )
    from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

    from koda.messages import Message
    from koda.providers.registry import ModelCapabilities

logger = get_logger(__name__)


@dataclass(slots=True)
class PartialToolCallState:
    call_id: str | None = None
    tool_name: str | None = None
    argument_chunks: list[str] = field(default_factory=list)

    def add_delta(self, tool_call: ChoiceDeltaToolCall) -> None:
        """Accumulate streamed tool-call fields into this partial state."""
        if tool_call.id:
            self.call_id = tool_call.id

        function = tool_call.function
        if function is None:
            return

        if function.name:
            self.tool_name = function.name
        if function.arguments:
            self.argument_chunks.append(function.arguments)

    def parse_arguments(self) -> dict[str, object]:
        """Parse buffered argument chunks into a JSON object."""
        raw_arguments = "".join(self.argument_chunks) or "{}"
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def to_tool_call_requested(self) -> ToolCallRequested | None:
        """Build a tool-call event when required fields are present."""
        if not self.call_id or not self.tool_name:
            return None
        arguments: dict[str, Any] = self.parse_arguments()
        return ToolCallRequested(
            call=ToolCall(
                tool_name=self.tool_name,
                arguments=arguments,
                call_id=self.call_id,
            ),
        )


class BergetAIProvider(Provider[BergetAIAdapter]):
    def __init__(
        self,
        api_key: str,
        model: str,
        adapter: BergetAIAdapter,
        base_url: str | None = "https://api.berget.ai/v1",
        capabilities: set[ModelCapabilities] | None = None,
    ) -> None:
        """Initialize the Berget provider client and runtime configuration."""
        if not api_key or not api_key.strip():
            logger.error("empty_api_key", provider="BergetAI")
            raise exceptions.EmptyApiKeyError("BergetAI")

        self.client: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model: str = model
        self.adapter: BergetAIAdapter = adapter
        self.capabilities: set[ModelCapabilities] = capabilities or set()

        logger.info("berget_provider_initialized", model=model)

    def _collect_tool_call_delta(
        self,
        partial_tool_calls: dict[int, PartialToolCallState],
        tool_call: ChoiceDeltaToolCall,
    ) -> None:
        """Collect one streamed tool-call delta by its index."""
        index = tool_call.index
        if index is None:
            return

        state = partial_tool_calls.setdefault(index, PartialToolCallState())
        state.add_delta(tool_call)

    def _emit_tool_calls(
        self,
        partial_tool_calls: dict[int, PartialToolCallState],
    ) -> list[ToolCallRequested]:
        """Emit completed tool-call events in stable index order."""
        events: list[ToolCallRequested] = []
        for idx in sorted(partial_tool_calls):
            event = partial_tool_calls[idx].to_tool_call_requested()
            if event:
                events.append(event)

        return events

    def _process_choice(
        self,
        choice: Choice,
        partial_tool_calls: dict[int, PartialToolCallState],
    ) -> list[ProviderEvent]:
        """Translate one streamed choice into provider events."""
        events: list[ProviderEvent] = []
        delta = choice.delta
        if delta is not None:
            if isinstance(delta.content, str) and delta.content:
                events.append(TextDelta(text=delta.content))
            for tool_call in delta.tool_calls or ():
                self._collect_tool_call_delta(partial_tool_calls, tool_call)

        if choice.finish_reason != "tool_calls":
            return events

        events.extend(self._emit_tool_calls(partial_tool_calls))
        partial_tool_calls.clear()
        return events

    async def _iter_stream_events(
        self,
        stream: AsyncStream[ChatCompletionChunk],
        partial_tool_calls: dict[int, PartialToolCallState],
    ) -> AsyncIterator[ProviderEvent]:
        """Yield provider events from streamed chat completion chunks."""
        async for chunk in stream:
            for choice in chunk.choices:
                for event in self._process_choice(choice, partial_tool_calls):
                    yield event

    async def stream(
        self,
        messages: Sequence[Message],
        system_message: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        """Run a streaming completion and emit text/tool-call events."""
        if not messages:
            logger.warning("stream_called_with_empty_messages")
            raise exceptions.EmptyMessagesListError

        logger.info("stream_started", message_count=len(messages))

        chat_messages: list[ChatCompletionMessageParam] = []
        if system_message:
            chat_messages.append(
                ChatCompletionSystemMessageParam(role="system", content=system_message),
            )
        chat_messages.extend(self.adapter.adapt_messages(messages))

        adapted_tools = self.adapter.adapt_tools(tools)
        partial_tool_calls: dict[int, PartialToolCallState] = {}

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=chat_messages,
                tools=adapted_tools,
                stream=True,
                parallel_tool_calls=True,
                prompt_cache_retention="24h",
            )
            async for event in self._iter_stream_events(stream, partial_tool_calls):
                yield event
            logger.info("stream_completed")
        except Exception as e:
            utils.handle_provider_exceptions(e, provider="BergetAI")
