from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Never

from anthropic import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncAnthropic,
    AuthenticationError,
    Omit,
    omit,
)
from anthropic import RateLimitError as AnthropicRateLimitError
from anthropic.lib.streaming import ContentBlockStopEvent, TextEvent
from anthropic.lib.streaming._types import ParsedMessageStreamEvent, ThinkingEvent
from anthropic.types import (
    ContentBlockParam,
    Message,
    MessageParam,
    OutputConfigParam,
    TextBlock,
    ThinkingBlock,
    ThinkingConfigParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlock,
    ToolUseBlockParam,
)
from pydantic import BaseModel

from koda.llm import exceptions
from koda.llm.protocols import LLM, LLMAdapter
from koda.llm.types import (
    LLMResponse,
    LLMResponseCompleted,
    LLMTextDelta,
    LLMThinkingDelta,
    LLMToolCallRequested,
)
from koda.messages import AssistantMessage, TokenUsage, ToolMessage
from koda.tools import ToolCall
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from koda.llm import LLMEvent
    from koda.llm.apis.base import LLMApiContext
    from koda.llm.models import ProviderModelConfig
    from koda.llm.types import LLMRequest
    from koda.messages import Message as KodaMessage
    from koda.tools import ToolDefinition


logger = get_logger(__name__)

type AnthropicMessagesLLMAdapter = LLMAdapter[
    list[MessageParam],
    list[ToolParam] | Omit,
    Message,
]

_ADAPTIVE_OUTPUT_CONFIGS: dict[str, OutputConfigParam] = {
    level: {"effort": level} for level in ("low", "medium", "high", "xhigh", "max")
}


@dataclass(frozen=True, slots=True)
class AnthropicMessagesAPIConfig:
    """Runtime configuration for the Anthropic Messages API."""

    api_key: str
    base_url: str
    model: str
    max_output_tokens: int
    thinking_budget_tokens: int | None = None


class AnthropicMessagesAdapter(
    LLMAdapter[
        list[MessageParam],
        list[ToolParam] | Omit,
        Message,
    ]
):
    """Convert between Koda messages/tools/responses and Anthropic Messages types."""

    @staticmethod
    def _text_block(text: str) -> ContentBlockParam:
        return {"type": "text", "text": text}

    @staticmethod
    def _to_tool_use_block(call: ToolCall) -> ToolUseBlockParam:
        return {
            "type": "tool_use",
            "id": call.call_id,
            "name": call.tool_name,
            "input": call.arguments,
        }

    @staticmethod
    def _to_tool_result_block(message: ToolMessage) -> ToolResultBlockParam:
        output = message.tool_result.output
        result_data: dict[str, object] = {
            "content": output.content,
            "is_error": output.is_error,
        }
        if output.error_message:
            result_data["error_message"] = output.error_message
        return {
            "type": "tool_result",
            "tool_use_id": message.tool_result.call_id,
            "content": json.dumps(result_data),
            "is_error": output.is_error,
        }

    def _to_provider_content(self, message: KodaMessage) -> str | list[ContentBlockParam]:
        if isinstance(message, ToolMessage):
            return [self._to_tool_result_block(message)]
        if isinstance(message, AssistantMessage):
            content: list[ContentBlockParam] = []
            if message.content:
                content.append(self._text_block(message.content))
            content.extend(self._to_tool_use_block(call) for call in message.tool_calls)
            return content or ""
        return message.content

    def to_provider_messages(self, messages: Sequence[KodaMessage]) -> list[MessageParam]:
        return [
            {
                "role": "assistant" if isinstance(message, AssistantMessage) else "user",
                "content": self._to_provider_content(message),
            }
            for message in messages
        ]

    def to_provider_tools(
        self,
        tools: Sequence[ToolDefinition] | None,
    ) -> list[ToolParam] | Omit:
        if not tools:
            return omit
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters_model.model_json_schema(),
            }
            for tool in tools
        ]

    @staticmethod
    def _text_from_response(response: Message) -> str:
        return "".join(block.text for block in response.content if isinstance(block, TextBlock))

    @staticmethod
    def _thinking_from_response(response: Message) -> str:
        return "".join(
            block.thinking for block in response.content if isinstance(block, ThinkingBlock)
        )

    @staticmethod
    def _tool_calls_from_response(response: Message) -> list[ToolCall]:
        return [
            ToolCall(tool_name=block.name, arguments=block.input, call_id=block.id)
            for block in response.content
            if isinstance(block, ToolUseBlock)
        ]

    @staticmethod
    def _usage_from_response(response: Message) -> TokenUsage:
        return TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cached_tokens=response.usage.cache_read_input_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
        )

    def to_llm_response(self, response: Message) -> LLMResponse[AssistantMessage]:
        return LLMResponse(
            output=AssistantMessage(
                content=self._text_from_response(response),
                thinking_content=self._thinking_from_response(response),
                tool_calls=self._tool_calls_from_response(response),
            ),
            usage=self._usage_from_response(response),
        )


def _resolve_thinking(
    *,
    thinking: str,
    budget_tokens: int | None,
    max_tokens: int,
) -> tuple[ThinkingConfigParam, OutputConfigParam | Omit]:
    if thinking == "enabled":
        if budget_tokens is None:
            raise exceptions.ThinkingBudgetTokensNotConfiguredError
        return {
            "type": "enabled",
            "budget_tokens": min(budget_tokens, max_tokens - 1),
            "display": "summarized",
        }, omit
    output_config = _ADAPTIVE_OUTPUT_CONFIGS.get(thinking)
    if output_config is not None:
        return {"type": "adaptive", "display": "summarized"}, output_config
    return {"type": "disabled"}, omit


def _or_omit[T](value: T | None) -> T | Omit:
    return value if value is not None else omit


def _coalesce[T](value: T | None, default: T) -> T:
    return value if value is not None else default


def _raise_anthropic_error(error: Exception, *, backend: str) -> Never:
    if isinstance(error, AnthropicRateLimitError):
        logger.error("llm_rate_limit_error", backend=backend)
        raise exceptions.LLMRateLimitError(backend, error) from error
    if isinstance(error, AuthenticationError):
        logger.error("llm_authentication_error", backend=backend)
        raise exceptions.LLMAuthenticationError(backend, error) from error
    if isinstance(error, APIConnectionError | APITimeoutError):
        logger.error("llm_connection_error", backend=backend, error=repr(error))
        raise exceptions.LLMConnectionError(backend, error) from error
    if isinstance(error, APIError):
        logger.error("llm_api_error", backend=backend, error=repr(error))
        raise exceptions.LLMAPIError(backend, error) from error
    raise error


def _thinking_budget_tokens(model: ProviderModelConfig) -> int | None:
    thinking = model.thinking
    return thinking.budget_tokens.max_tokens if thinking.budget_tokens else None


class AnthropicMessagesEventAdapter:
    """Convert Anthropic streaming events into Koda LLM stream events."""

    @staticmethod
    def _coerce_tool_input(value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            raise exceptions.InvalidToolCallArgumentsError
        parsed: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise exceptions.InvalidToolCallArgumentsError
            parsed[key] = item
        return parsed

    @staticmethod
    def _tool_call_from_content_block_stop(
        event: ContentBlockStopEvent,
    ) -> LLMToolCallRequested | None:
        block = event.content_block
        if not isinstance(block, ToolUseBlock):
            return None
        return LLMToolCallRequested(
            call=ToolCall(
                tool_name=block.name,
                arguments=AnthropicMessagesEventAdapter._coerce_tool_input(block.input),
                call_id=block.id,
            )
        )

    def to_llm_event(self, event: ParsedMessageStreamEvent[Any]) -> LLMEvent | None:
        if isinstance(event, TextEvent):
            return LLMTextDelta(text=event.text)
        if isinstance(event, ThinkingEvent):
            return LLMThinkingDelta(text=event.thinking)
        if isinstance(event, ContentBlockStopEvent):
            return self._tool_call_from_content_block_stop(event)
        return None


class AnthropicMessagesAPI(LLM):
    """Concrete LLM implementation backed by Anthropic's Messages API."""

    def __init__(
        self,
        config: AnthropicMessagesAPIConfig,
        *,
        client: AsyncAnthropic,
        adapter: AnthropicMessagesLLMAdapter,
        event_adapter: AnthropicMessagesEventAdapter,
    ) -> None:
        self.config = config
        self.client = client
        self.adapter = adapter
        self.event_adapter = event_adapter

    @classmethod
    def from_context(cls, context: LLMApiContext) -> AnthropicMessagesAPI:
        """Create an Anthropic Messages API from a resolved model-catalog context."""
        config = AnthropicMessagesAPIConfig(
            api_key=context.require_api_key(),
            base_url=context.provider.base_url,
            model=context.model.id,
            max_output_tokens=context.require_max_output_tokens(),
            thinking_budget_tokens=_thinking_budget_tokens(context.model),
        )
        return cls(
            config,
            client=AsyncAnthropic(api_key=config.api_key, base_url=config.base_url),
            adapter=AnthropicMessagesAdapter(),
            event_adapter=AnthropicMessagesEventAdapter(),
        )

    @staticmethod
    def _missing_tool_calls(
        response: LLMResponse[AssistantMessage],
        emitted_ids: set[str],
    ) -> list[ToolCall]:
        return [call for call in response.output.tool_calls if call.call_id not in emitted_ids]

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        max_tokens = _coalesce(request.options.max_output_tokens, self.config.max_output_tokens)
        thinking, output_config = _resolve_thinking(
            thinking=request.options.thinking,
            budget_tokens=self.config.thinking_budget_tokens,
            max_tokens=max_tokens,
        )
        try:
            response = await self.client.messages.create(
                cache_control={"type": "ephemeral", "ttl": "1h"},
                max_tokens=max_tokens,
                messages=self.adapter.to_provider_messages(request.messages),
                model=self.config.model,
                output_config=output_config,
                system=request.instructions or "",
                temperature=_or_omit(request.options.temperature),
                thinking=thinking,
                tools=self.adapter.to_provider_tools(request.tools),
                top_p=_or_omit(request.options.top_p),
            )
        except Exception as error:
            _raise_anthropic_error(error, backend="anthropic-messages")
        return self.adapter.to_llm_response(response)

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:  # noqa: C901
        max_tokens = _coalesce(request.options.max_output_tokens, self.config.max_output_tokens)
        thinking, output_config = _resolve_thinking(
            thinking=request.options.thinking,
            budget_tokens=self.config.thinking_budget_tokens,
            max_tokens=max_tokens,
        )
        emitted_tool_call_ids: set[str] = set()
        try:
            async with self.client.messages.stream(
                cache_control={"type": "ephemeral", "ttl": "1h"},
                max_tokens=max_tokens,
                messages=self.adapter.to_provider_messages(request.messages),
                model=self.config.model,
                output_config=output_config,
                system=request.instructions or "",
                temperature=_or_omit(request.options.temperature),
                thinking=thinking,
                tools=self.adapter.to_provider_tools(request.tools),
                top_p=_or_omit(request.options.top_p),
            ) as stream:
                async for event in stream:
                    processed_event = self.event_adapter.to_llm_event(event)
                    if isinstance(processed_event, LLMToolCallRequested):
                        emitted_tool_call_ids.add(processed_event.call.call_id)
                    if processed_event is not None:
                        yield processed_event
                response = await stream.get_final_message()
        except Exception as error:
            _raise_anthropic_error(error, backend="anthropic-messages")
        adapted_response = self.adapter.to_llm_response(response)
        for tool_call in self._missing_tool_calls(adapted_response, emitted_tool_call_ids):
            yield LLMToolCallRequested(call=tool_call)
        yield LLMResponseCompleted(response=adapted_response)

    async def generate_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> LLMResponse[T]:
        _ = request, schema
        raise exceptions.StructuredOutputNotSupportedError
