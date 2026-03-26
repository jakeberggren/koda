from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from openai import AsyncOpenAI, Omit, OpenAIError, omit
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion_system_message_param import (
    ChatCompletionSystemMessageParam,
)
from openai.types.chat.chat_completion_tool_union_param import ChatCompletionToolUnionParam
from pydantic import BaseModel

from koda.llm import LLMEvent, LLMResponse
from koda.llm.exceptions import (
    InvalidToolCallArgumentsError,
    StructuredOutputNotSupportedError,
)
from koda.llm.protocols import LLM, LLMAdapter
from koda.llm.types import (
    LLMResponseCompleted,
    LLMTextDelta,
    LLMToolCallRequested,
)
from koda.llm.utils import raise_llm_error_from_openai
from koda.messages import AssistantMessage, TokenUsage
from koda.tools import ToolCall

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from openai.types.chat.chat_completion_chunk import (
        ChatCompletionChunk,
        Choice,
        ChoiceDeltaToolCall,
    )
    from openai.types.chat.completion_create_params import ReasoningEffort
    from openai.types.completion_usage import CompletionUsage

    from koda.llm.models import ThinkingOptionId
    from koda.llm.types import LLMRequest


type CompletionsAdapter = LLMAdapter[
    list[ChatCompletionMessageParam],
    list[ChatCompletionToolUnionParam] | Omit,
    ChatCompletion,
]
type OpenAIClientFactory = Callable[..., AsyncOpenAI]
type CompletionsReasoningResolver = Callable[[ThinkingOptionId], ReasoningEffort | Omit]


@dataclass(frozen=True, slots=True)
class _CreateParams:
    logprobs: bool | Omit
    messages: list[ChatCompletionMessageParam]
    max_completion_tokens: int | Omit
    model: str
    parallel_tool_calls: bool | Omit
    prompt_cache_retention: Literal["24h"] | Omit
    reasoning: ReasoningEffort | Omit
    temperature: float | Omit
    tools: list[ChatCompletionToolUnionParam] | Omit
    top_logprobs: int | Omit
    top_p: float | Omit


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
    except json.JSONDecodeError as exc:
        raise InvalidToolCallArgumentsError from exc
    if not isinstance(parsed, dict):
        raise InvalidToolCallArgumentsError
    return parsed


@dataclass(frozen=True, slots=True)
class CompletionsDriverConfig:
    api_key: str
    model: str
    base_url: str | None = None


class CompletionsDriver(LLM):
    def __init__(
        self,
        config: CompletionsDriverConfig,
        *,
        adapter: CompletionsAdapter,
        reasoning_resolver: CompletionsReasoningResolver,
        client_factory: OpenAIClientFactory = AsyncOpenAI,
    ) -> None:
        self.config: CompletionsDriverConfig = config
        self.adapter: CompletionsAdapter = adapter
        self.reasoning_resolver = reasoning_resolver
        self.client: AsyncOpenAI = client_factory(api_key=config.api_key, base_url=config.base_url)

    @staticmethod
    def _to_omit[T](value: T | None) -> T | Omit:
        return value if value is not None else omit

    def _resolve_messages(self, request: LLMRequest) -> list[ChatCompletionMessageParam]:
        messages = list(self.adapter.to_provider_messages(request.messages))
        if request.instructions:
            return [
                ChatCompletionSystemMessageParam(role="system", content=request.instructions),
                *messages,
            ]
        return messages

    def _resolve_prompt_cache_retention(
        self, *, extended_prompt_retention: bool
    ) -> Literal["24h"] | Omit:
        return self._to_omit("24h" if extended_prompt_retention else None)

    @staticmethod
    def _resolve_logprobs(*, top_logprobs: int | None) -> bool | Omit:
        return True if top_logprobs is not None else omit

    def _resolve_create_params(self, request: LLMRequest) -> _CreateParams:
        return _CreateParams(
            logprobs=self._resolve_logprobs(top_logprobs=request.options.top_logprobs),
            messages=self._resolve_messages(request),
            max_completion_tokens=self._to_omit(request.options.max_output_tokens),
            model=self.config.model,
            parallel_tool_calls=(request.options.parallel_tool_calls if request.tools else omit),
            prompt_cache_retention=self._resolve_prompt_cache_retention(
                extended_prompt_retention=request.options.extended_prompt_retention
            ),
            reasoning=self.reasoning_resolver(request.options.thinking),
            temperature=self._to_omit(request.options.temperature),
            tools=self.adapter.to_provider_tools(request.tools),
            top_logprobs=self._to_omit(request.options.top_logprobs),
            top_p=self._to_omit(request.options.top_p),
        )

    @staticmethod
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

    def _adapt_response(self, response: ChatCompletion) -> LLMResponse[AssistantMessage]:
        message = response.choices[0].message
        tool_calls = self.adapter.extract_tool_calls(response)
        content = message.content or ""
        return self._build_response(
            content=content,
            tool_calls=tool_calls,
            usage=self._adapt_usage(response.usage),
        )

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        create_params = self._resolve_create_params(request)
        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                logprobs=create_params.logprobs,
                messages=create_params.messages,
                max_completion_tokens=create_params.max_completion_tokens,
                model=create_params.model,
                parallel_tool_calls=create_params.parallel_tool_calls,
                prompt_cache_retention=create_params.prompt_cache_retention,
                reasoning_effort=create_params.reasoning,
                temperature=create_params.temperature,
                tools=create_params.tools,
                top_logprobs=create_params.top_logprobs,
                top_p=create_params.top_p,
            )
            return self._adapt_response(response)
        except OpenAIError as e:
            raise_llm_error_from_openai(e, backend="completions")

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
    def _materialize_tool_calls(
        partial_tool_calls: dict[int, _PartialToolCallState],
    ) -> list[ToolCall]:
        return [
            tool_call
            for state in (partial_tool_calls[idx] for idx in sorted(partial_tool_calls))
            if (tool_call := state.to_tool_call()) is not None
        ]

    def _process_choice_delta(
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

    def _process_choice(
        self,
        choice: Choice,
        completed_tool_calls: list[ToolCall],
        partial_tool_calls: dict[int, _PartialToolCallState],
        text_chunks: list[str],
    ) -> Iterator[LLMEvent]:
        yield from self._process_choice_delta(choice, partial_tool_calls, text_chunks)

        if choice.finish_reason != "tool_calls":
            return

        tool_calls = self._materialize_tool_calls(partial_tool_calls)
        completed_tool_calls.extend(tool_calls)
        partial_tool_calls.clear()
        for tool_call in tool_calls:
            yield LLMToolCallRequested(call=tool_call)

    def _process_stream_chunk(
        self,
        chunk: ChatCompletionChunk,
        completed_tool_calls: list[ToolCall],
        partial_tool_calls: dict[int, _PartialToolCallState],
        text_chunks: list[str],
    ) -> Iterator[LLMEvent]:
        for choice in chunk.choices:
            yield from self._process_choice(
                choice,
                completed_tool_calls,
                partial_tool_calls,
                text_chunks,
            )

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        create_params = self._resolve_create_params(request)
        completed_tool_calls: list[ToolCall] = []
        partial_tool_calls: dict[int, _PartialToolCallState] = {}
        text_chunks: list[str] = []
        usage: TokenUsage | None = None
        try:
            stream = await self.client.chat.completions.create(
                logprobs=create_params.logprobs,
                messages=create_params.messages,
                max_completion_tokens=create_params.max_completion_tokens,
                model=create_params.model,
                parallel_tool_calls=create_params.parallel_tool_calls,
                prompt_cache_retention=create_params.prompt_cache_retention,
                reasoning_effort=create_params.reasoning,
                stream=True,
                stream_options={"include_usage": True},
                temperature=create_params.temperature,
                tools=create_params.tools,
                top_logprobs=create_params.top_logprobs,
                top_p=create_params.top_p,
            )
            async for chunk in stream:
                if chunk.usage is not None:
                    usage = self._adapt_usage(chunk.usage)
                for processed_event in self._process_stream_chunk(
                    chunk,
                    completed_tool_calls,
                    partial_tool_calls,
                    text_chunks,
                ):
                    yield processed_event
            tool_calls = [
                *completed_tool_calls,
                *self._materialize_tool_calls(partial_tool_calls),
            ]
            yield LLMResponseCompleted(
                response=self._build_response(
                    content="".join(text_chunks),
                    tool_calls=tool_calls,
                    usage=usage,
                )
            )
        except OpenAIError as e:
            raise_llm_error_from_openai(e, backend="completions")

    async def generate_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> LLMResponse[T]:
        _ = request, schema
        raise StructuredOutputNotSupportedError
