from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from openai import AsyncOpenAI, Omit, OpenAIError, omit
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_assistant_message_param import (
    ChatCompletionAssistantMessageParam,
)
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.chat.chat_completion_message_function_tool_call_param import (
    ChatCompletionMessageFunctionToolCallParam,
)
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion_system_message_param import (
    ChatCompletionSystemMessageParam,
)
from openai.types.chat.chat_completion_tool_message_param import ChatCompletionToolMessageParam
from openai.types.chat.chat_completion_tool_union_param import ChatCompletionToolUnionParam
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam
from pydantic import BaseModel

from koda.llm import exceptions
from koda.llm.apis.credentials import resolve_api_key_credential
from koda.llm.protocols import LLM, LLMAdapter
from koda.llm.types import (
    LLMResponse,
    LLMResponseCompleted,
    LLMTextDelta,
    LLMToolCallRequested,
)
from koda.llm.utils import raise_llm_error_from_openai, resolve_openai_client
from koda.messages import AssistantMessage, TokenUsage, ToolMessage, UserMessage
from koda.tools import ToolCall

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator, Sequence

    from openai.types.chat.chat_completion_chunk import (
        ChatCompletionChunk,
        Choice,
        ChoiceDeltaToolCall,
    )
    from openai.types.completion_usage import CompletionUsage

    from koda.llm import LLMEvent
    from koda.llm.apis.base import LLMApiContext
    from koda.llm.types import LLMRequest
    from koda.messages import Message
    from koda.tools import ToolDefinition


type OpenAICompletionsLLMAdapter = LLMAdapter[
    list[ChatCompletionMessageParam],
    list[ChatCompletionToolUnionParam] | Omit,
    ChatCompletion,
]


@dataclass(frozen=True, slots=True)
class OpenAICompletionsAPIConfig:
    """Runtime configuration for an OpenAI-compatible Chat Completions API."""

    api_key: str
    base_url: str
    model: str


@dataclass(slots=True)
class _PartialToolCallState:
    call_id: str | None = None
    tool_name: str | None = None
    argument_chunks: list[str] = field(default_factory=list)

    def add_delta(self, tool_call: ChoiceDeltaToolCall) -> None:
        if tool_call.id:
            self.call_id = tool_call.id

        function = tool_call.function
        if function is None:
            return
        if function.name:
            self.tool_name = function.name
        if function.arguments:
            self.argument_chunks.append(function.arguments)

    def raw_arguments(self) -> str:
        return "".join(self.argument_chunks) or "{}"

    def to_tool_call(self) -> ToolCall | None:
        if not self.call_id or not self.tool_name:
            return None
        return ToolCall(
            tool_name=self.tool_name,
            arguments=_parse_tool_call_arguments(self.raw_arguments()),
            call_id=self.call_id,
        )


def _parse_tool_call_arguments(raw_arguments: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError as error:
        raise exceptions.InvalidToolCallArgumentsError from error
    if not isinstance(parsed, dict):
        raise exceptions.InvalidToolCallArgumentsError
    return parsed


def _or_omit[T](value: T | None) -> T | Omit:
    return value if value is not None else omit


class OpenAICompletionsAdapter(
    LLMAdapter[
        list[ChatCompletionMessageParam],
        list[ChatCompletionToolUnionParam] | Omit,
        ChatCompletion,
    ]
):
    """Convert between Koda messages/tools/responses and Chat Completions types."""

    @staticmethod
    def _to_provider_tool_message(message: ToolMessage) -> ChatCompletionToolMessageParam:
        tool_output = message.tool_result.output
        payload: dict[str, Any] = {
            "content": tool_output.content,
            "is_error": tool_output.is_error,
        }
        if tool_output.error_message:
            payload["error_message"] = tool_output.error_message

        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=message.tool_result.call_id,
            content=json.dumps(payload),
        )

    @staticmethod
    def _to_provider_user_message(message: UserMessage) -> ChatCompletionUserMessageParam:
        return ChatCompletionUserMessageParam(role="user", content=message.content)

    @staticmethod
    def _to_provider_assistant_message(
        message: AssistantMessage,
    ) -> ChatCompletionAssistantMessageParam:
        if message.tool_calls:
            tool_calls = [
                ChatCompletionMessageFunctionToolCallParam(
                    id=tool_call.call_id,
                    type="function",
                    function={
                        "name": tool_call.tool_name,
                        "arguments": json.dumps(tool_call.arguments),
                    },
                )
                for tool_call in message.tool_calls
            ]
            return ChatCompletionAssistantMessageParam(
                role="assistant",
                content=message.content,
                tool_calls=tool_calls,
            )
        return ChatCompletionAssistantMessageParam(role="assistant", content=message.content)

    def to_provider_messages(self, messages: Sequence[Message]) -> list[ChatCompletionMessageParam]:
        result: list[ChatCompletionMessageParam] = []
        for message in messages:
            if isinstance(message, ToolMessage):
                result.append(self._to_provider_tool_message(message))
                continue
            if isinstance(message, UserMessage):
                result.append(self._to_provider_user_message(message))
                continue
            if isinstance(message, AssistantMessage):
                result.append(self._to_provider_assistant_message(message))
                continue
            raise exceptions.UnknownMessageTypeError(type(message))
        return result

    @staticmethod
    def _remove_null_type_from_anyof(options: list[Any]) -> list[Any]:
        return [
            option
            for option in options
            if not (isinstance(option, dict) and option.get("type") == "null")
        ]

    def _merge_single_anyof_object(
        self,
        result: dict[str, Any],
        options: list[Any],
    ) -> bool:
        if len(options) != 1 or not isinstance(options[0], dict):
            return False
        inner = self._simplify_schema(options[0])
        if not isinstance(inner, dict):
            return False
        for inner_key, inner_value in inner.items():
            if inner_key not in result:
                result[inner_key] = inner_value
        return True

    def _simplify_schema_dict(self, value: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, raw in value.items():
            if key == "$schema":
                continue
            if key == "anyOf" and isinstance(raw, list):
                non_null = self._remove_null_type_from_anyof(raw)
                if self._merge_single_anyof_object(result, non_null):
                    continue
                result[key] = self._simplify_schema(non_null if non_null else raw)
                continue
            result[key] = self._simplify_schema(raw)
        return result

    def _simplify_schema(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._simplify_schema(item) for item in value]
        if isinstance(value, dict):
            return self._simplify_schema_dict(value)
        return value

    def _to_provider_tool_definition(self, tool: ToolDefinition) -> ChatCompletionToolUnionParam:
        schema = self._simplify_schema(tool.parameters_model.model_json_schema())
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "strict": True,
                "parameters": schema,
            },
        }

    def to_provider_tools(
        self,
        tools: Sequence[ToolDefinition] | None,
    ) -> list[ChatCompletionToolUnionParam] | Omit:
        if not tools:
            return omit
        return [self._to_provider_tool_definition(tool) for tool in tools]

    def _extract_tool_calls(self, response: ChatCompletion) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for choice in response.choices:
            for tool_call in choice.message.tool_calls or ():
                if not isinstance(tool_call, ChatCompletionMessageFunctionToolCall):
                    continue
                calls.append(
                    ToolCall(
                        tool_name=tool_call.function.name,
                        arguments=_parse_tool_call_arguments(tool_call.function.arguments),
                        call_id=tool_call.id,
                    )
                )
        return calls

    @staticmethod
    def _adapt_usage(response: ChatCompletion) -> TokenUsage | None:
        usage = response.usage
        if usage is None:
            return None
        return _adapt_usage(usage)

    def to_llm_response(self, response: ChatCompletion) -> LLMResponse[AssistantMessage]:
        message = response.choices[0].message
        return LLMResponse(
            output=AssistantMessage(
                content=message.content or "",
                tool_calls=self._extract_tool_calls(response),
            ),
            usage=self._adapt_usage(response),
        )


class OpenAICompletionsEventAdapter:
    """Convert Chat Completions streaming chunks into Koda LLM stream events."""

    @staticmethod
    def _collect_tool_call_delta(
        partial_tool_calls: dict[int, _PartialToolCallState],
        tool_call: ChoiceDeltaToolCall,
    ) -> None:
        index = tool_call.index
        if index is None:
            return
        state = partial_tool_calls.setdefault(index, _PartialToolCallState())
        state.add_delta(tool_call)

    @staticmethod
    def materialize_tool_calls(
        partial_tool_calls: dict[int, _PartialToolCallState],
    ) -> list[ToolCall]:
        return [
            tool_call
            for state in (partial_tool_calls[idx] for idx in sorted(partial_tool_calls))
            if (tool_call := state.to_tool_call()) is not None
        ]

    def _events_from_choice_delta(
        self,
        choice: Choice,
        partial_tool_calls: dict[int, _PartialToolCallState],
        text_chunks: list[str],
    ) -> Iterator[LLMEvent]:
        delta = choice.delta
        if delta is None:
            return
        if isinstance(delta.content, str) and delta.content:
            text_chunks.append(delta.content)
            yield LLMTextDelta(text=delta.content)
        for tool_call in delta.tool_calls or ():
            self._collect_tool_call_delta(partial_tool_calls, tool_call)

    def _events_from_choice(
        self,
        choice: Choice,
        completed_tool_calls: list[ToolCall],
        partial_tool_calls: dict[int, _PartialToolCallState],
        text_chunks: list[str],
    ) -> Iterator[LLMEvent]:
        yield from self._events_from_choice_delta(choice, partial_tool_calls, text_chunks)

        if choice.finish_reason != "tool_calls":
            return

        tool_calls = self.materialize_tool_calls(partial_tool_calls)
        completed_tool_calls.extend(tool_calls)
        partial_tool_calls.clear()
        for tool_call in tool_calls:
            yield LLMToolCallRequested(call=tool_call)

    def to_llm_events(
        self,
        chunk: ChatCompletionChunk,
        completed_tool_calls: list[ToolCall],
        partial_tool_calls: dict[int, _PartialToolCallState],
        text_chunks: list[str],
    ) -> Iterator[LLMEvent]:
        for choice in chunk.choices:
            yield from self._events_from_choice(
                choice,
                completed_tool_calls,
                partial_tool_calls,
                text_chunks,
            )


def _adapt_usage(usage: CompletionUsage | None) -> TokenUsage | None:
    if usage is None:
        return None
    prompt_tokens_details = usage.prompt_tokens_details
    cached_tokens = (
        prompt_tokens_details.cached_tokens if prompt_tokens_details is not None else None
    )

    return TokenUsage(
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        cached_tokens=cached_tokens,
        total_tokens=usage.total_tokens,
    )


class OpenAICompletionsAPI(LLM):
    """Concrete LLM implementation backed by an OpenAI-compatible Chat Completions API."""

    def __init__(
        self,
        config: OpenAICompletionsAPIConfig,
        *,
        client: AsyncOpenAI,
        adapter: OpenAICompletionsLLMAdapter,
        event_adapter: OpenAICompletionsEventAdapter,
    ) -> None:
        self.config = config
        self.client = client
        self.adapter = adapter
        self.event_adapter = event_adapter

    @classmethod
    async def from_context(cls, context: LLMApiContext) -> OpenAICompletionsAPI:
        """Create a Chat Completions API from a resolved model-catalog context."""
        config = OpenAICompletionsAPIConfig(
            api_key=resolve_api_key_credential(context),
            base_url=context.connection.base_url,
            model=context.model.id,
        )
        client_factory = resolve_openai_client(context.settings)
        return cls(
            config,
            client=client_factory(api_key=config.api_key, base_url=config.base_url),
            adapter=OpenAICompletionsAdapter(),
            event_adapter=OpenAICompletionsEventAdapter(),
        )

    def _resolve_messages(self, request: LLMRequest) -> list[ChatCompletionMessageParam]:
        messages = list(self.adapter.to_provider_messages(request.messages))
        if request.instructions:
            return [
                ChatCompletionSystemMessageParam(role="system", content=request.instructions),
                *messages,
            ]
        return messages

    @staticmethod
    def _resolve_prompt_cache_retention(
        *, extended_prompt_retention: bool
    ) -> Literal["24h"] | Omit:
        return _or_omit("24h" if extended_prompt_retention else None)

    @staticmethod
    def _resolve_logprobs(*, top_logprobs: int | None) -> bool | Omit:
        return True if top_logprobs is not None else omit

    @staticmethod
    def _build_response(
        *,
        content: str,
        tool_calls: list[ToolCall],
        usage: TokenUsage | None,
    ) -> LLMResponse[AssistantMessage]:
        return LLMResponse(
            output=AssistantMessage(content=content, tool_calls=tool_calls),
            usage=usage,
        )

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        try:
            response = await self.client.chat.completions.create(
                logprobs=self._resolve_logprobs(top_logprobs=request.options.top_logprobs),
                messages=self._resolve_messages(request),
                max_completion_tokens=_or_omit(request.options.max_output_tokens),
                model=self.config.model,
                parallel_tool_calls=(
                    request.options.parallel_tool_calls if request.tools else omit
                ),
                prompt_cache_retention=self._resolve_prompt_cache_retention(
                    extended_prompt_retention=request.options.extended_prompt_retention
                ),
                reasoning_effort=omit,
                temperature=_or_omit(request.options.temperature),
                tools=self.adapter.to_provider_tools(request.tools),
                top_logprobs=_or_omit(request.options.top_logprobs),
                top_p=_or_omit(request.options.top_p),
            )
        except OpenAIError as error:
            raise_llm_error_from_openai(error, backend="openai-completions")
        return self.adapter.to_llm_response(response)

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        completed_tool_calls: list[ToolCall] = []
        partial_tool_calls: dict[int, _PartialToolCallState] = {}
        text_chunks: list[str] = []
        usage: TokenUsage | None = None
        try:
            stream = await self.client.chat.completions.create(
                logprobs=self._resolve_logprobs(top_logprobs=request.options.top_logprobs),
                messages=self._resolve_messages(request),
                max_completion_tokens=_or_omit(request.options.max_output_tokens),
                model=self.config.model,
                parallel_tool_calls=(
                    request.options.parallel_tool_calls if request.tools else omit
                ),
                prompt_cache_retention=self._resolve_prompt_cache_retention(
                    extended_prompt_retention=request.options.extended_prompt_retention
                ),
                reasoning_effort=omit,
                stream=True,
                stream_options={"include_usage": True},
                temperature=_or_omit(request.options.temperature),
                tools=self.adapter.to_provider_tools(request.tools),
                top_logprobs=_or_omit(request.options.top_logprobs),
                top_p=_or_omit(request.options.top_p),
            )
            async for chunk in stream:
                if chunk.usage is not None:
                    usage = _adapt_usage(chunk.usage)
                for processed_event in self.event_adapter.to_llm_events(
                    chunk,
                    completed_tool_calls,
                    partial_tool_calls,
                    text_chunks,
                ):
                    yield processed_event
            tool_calls = [
                *completed_tool_calls,
                *self.event_adapter.materialize_tool_calls(partial_tool_calls),
            ]
            yield LLMResponseCompleted(
                response=self._build_response(
                    content="".join(text_chunks),
                    tool_calls=tool_calls,
                    usage=usage,
                )
            )
        except OpenAIError as error:
            raise_llm_error_from_openai(error, backend="openai-completions")

    async def generate_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> LLMResponse[T]:
        _ = request, schema
        raise exceptions.StructuredOutputNotSupportedError
