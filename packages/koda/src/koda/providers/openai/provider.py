from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from typing import Literal

from openai import AsyncOpenAI, Omit, omit
from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseFunctionWebSearch,
    ResponseOutputItemDoneEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ResponseWebSearchCallInProgressEvent,
    ToolParam,
    WebSearchToolParam,
)
from openai.types.responses.response_function_web_search import ActionSearch

from koda.messages import Message
from koda.providers import Provider, exceptions, utils
from koda.providers.events import (
    ProviderEvent,
    ProviderToolCompleted,
    ProviderToolStarted,
    TextDelta,
    ToolCallRequested,
)
from koda.providers.openai import OpenAIAdapter
from koda.providers.registry import ModelCapabilities
from koda.tools import ToolCall, ToolDefinition, ToolOutput, ToolResult
from koda_common.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(Provider[OpenAIAdapter]):
    def __init__(  # noqa: PLR0913 - ignore for now...
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        capabilities: set[ModelCapabilities] | None = None,
        client_factory: Callable[..., AsyncOpenAI] = AsyncOpenAI,
        *,
        allow_extended_prompt_retention: bool = False,
    ) -> None:
        if not api_key or not api_key.strip():
            logger.error("empty_api_key", provider="OpenAI")
            raise exceptions.EmptyApiKeyError("OpenAI")

        self.client: AsyncOpenAI = client_factory(api_key=api_key, base_url=base_url)
        self.model: str = model
        self.adapter: OpenAIAdapter = OpenAIAdapter()
        self.capabilities: set[ModelCapabilities] = capabilities or set()
        self.allow_extended_prompt_retention: bool = allow_extended_prompt_retention

        logger.info("openai_provider_initialized", model=model)

    def _build_tools(self, tools: list[ToolDefinition] | None) -> list[ToolParam]:
        """Combine agent tools with capability-based provider tools."""
        result: list[ToolParam] = []
        adapted_tools = self.adapter.adapt_tools(tools)
        if not isinstance(adapted_tools, Omit):
            result.extend(adapted_tools)
        if ModelCapabilities.WEB_SEARCH in self.capabilities:
            result.append(WebSearchToolParam(type="web_search"))
        return result

    @staticmethod
    def _format_web_search(output: ResponseFunctionWebSearch) -> str | None:
        """Build a display string from a web search output item."""
        action = output.action
        if not isinstance(action, ActionSearch):
            return None
        return f'Searched for "{action.query}"'

    def _resolve_prompt_cache_retention_strategy(self) -> Literal["24h"] | Omit:
        if (
            self.allow_extended_prompt_retention
            and ModelCapabilities.EXTENDED_PROMPT_RETENTION in self.capabilities
        ):
            return "24h"
        return omit

    def _process_event(  # noqa: C901
        self,
        event: ResponseStreamEvent,
    ) -> Iterator[ProviderEvent]:
        if isinstance(event, ResponseTextDeltaEvent):
            yield TextDelta(text=event.delta)
        elif isinstance(event, ResponseWebSearchCallInProgressEvent):
            call = ToolCall(tool_name="web_search", call_id=event.item_id, arguments={})
            yield ProviderToolStarted(call=call)
        elif isinstance(event, ResponseOutputItemDoneEvent) and isinstance(
            event.item, ResponseFunctionWebSearch
        ):
            output = ToolOutput(
                display=self._format_web_search(event.item),
                is_error=event.item.status == "failed",
            )
            result = ToolResult(output=output, call_id=event.item.id)
            yield ProviderToolCompleted(tool_name="web_search", result=result)
        elif isinstance(event, ResponseCompletedEvent):
            tool_calls = self.adapter.parse_tool_calls(event.response)
            for call in tool_calls:
                yield ToolCallRequested(call=call)

    async def stream(
        self,
        messages: Sequence[Message],
        system_message: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        if not messages:
            logger.warning("stream_called_with_empty_messages")
            raise exceptions.EmptyMessagesListError

        logger.info("stream_started", message_count=len(messages))

        openai_input = self.adapter.adapt_messages(messages)
        openai_tools = self._build_tools(tools)
        prompt_cache_retention = self._resolve_prompt_cache_retention_strategy()

        try:
            stream = await self.client.responses.create(
                model=self.model,
                instructions=system_message,
                stream=True,
                tools=openai_tools,
                input=openai_input,
                parallel_tool_calls=True,
                prompt_cache_retention=prompt_cache_retention,
            )
            async for event in stream:
                for processed_event in self._process_event(event):
                    yield processed_event
            logger.info("stream_completed")
        except Exception as e:
            utils.handle_provider_exceptions(e, provider="OpenAI")
