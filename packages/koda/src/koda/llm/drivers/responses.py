from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from openai import AsyncOpenAI, Omit, omit
from openai.types.responses import (
    FunctionToolParam,
    Response,
    ResponseCompletedEvent,
    ResponseFunctionWebSearch,
    ResponseInputParam,
    ResponseOutputItemDoneEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ResponseWebSearchCallInProgressEvent,
)
from openai.types.responses.response_function_web_search import ActionSearch

from koda.llm import LLMEvent, LLMResponse, LLMTokenUsage
from koda.llm.protocols import LLM, LLMAdapter
from koda.llm.types import (
    LLMResponseCompleted,
    LLMTextDelta,
    LLMToolCallRequested,
    LLMToolCompleted,
    LLMToolStarted,
)
from koda.llm.utils import raise_llm_error_from_openai
from koda.messages import AssistantMessage
from koda.tools import ToolCall, ToolOutput, ToolResult
from koda_common.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from koda.llm.types import LLMRequest


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ResponsesDriverConfig:
    api_key: str
    model: str
    base_url: str | None = None


@dataclass(frozen=True, slots=True)
class _CreateParams:
    input: ResponseInputParam
    model: str
    parallel_tool_calls: bool
    prompt_cache_retention: Literal["24h"] | Omit
    temperature: float | Omit
    tools: list[FunctionToolParam] | Omit
    top_logprobs: int | Omit
    top_p: float | Omit
    truncation: Literal["auto", "disabled"] | Omit


class ResponsesDriver(LLM):
    def __init__(
        self,
        config: ResponsesDriverConfig,
        *,
        adapter: ResponsesDriverAdapter | None = None,
        client_factory: Callable[..., AsyncOpenAI] = AsyncOpenAI,
    ) -> None:
        self.config: ResponsesDriverConfig = config
        self.adapter: ResponsesDriverAdapter = adapter or ResponsesDriverAdapter()
        self.client: AsyncOpenAI = client_factory(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    @staticmethod
    def _to_omit[T](value: T | None) -> T | Omit:
        return value if value is not None else omit

    def _resolve_prompt_cache_retention(
        self, *, extended_prompt_retention: bool
    ) -> Literal["24h"] | Omit:
        return self._to_omit("24h" if extended_prompt_retention else None)

    def _resolve_create_params(self, request: LLMRequest) -> _CreateParams:
        return _CreateParams(
            input=self.adapter.adapt_messages(request.messages),
            model=self.config.model,
            parallel_tool_calls=request.options.parallel_tool_calls,
            prompt_cache_retention=self._resolve_prompt_cache_retention(
                extended_prompt_retention=request.options.extended_prompt_retention
            ),
            temperature=self._to_omit(request.options.temperature),
            tools=self.adapter.adapt_tools(request.tools),
            top_logprobs=self._to_omit(request.options.top_logprobs),
            top_p=self._to_omit(request.options.top_p),
            truncation=self._to_omit(request.options.truncation),
        )

    @staticmethod
    def _format_web_search(output: ResponseFunctionWebSearch) -> str | None:
        action = output.action
        if not isinstance(action, ActionSearch):
            return None
        return f'Searched for "{action.query}"'

    @staticmethod
    def _adapt_usage(response: Response) -> LLMTokenUsage | None:
        usage = response.usage
        if usage is None:
            return None
        return LLMTokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.input_tokens_details.cached_tokens,
            total_tokens=usage.total_tokens,
        )

    def _adapt_response(self, response: Response) -> LLMResponse[AssistantMessage]:
        return LLMResponse(
            output=AssistantMessage(
                content=response.output_text or "",
                tool_calls=self.adapter.parse_tool_calls(response),
            ),
            usage=self._adapt_usage(response),
        )

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        create_params = self._resolve_create_params(request)
        try:
            response: Response = await self.client.responses.create(
                input=create_params.input,
                model=create_params.model,
                parallel_tool_calls=create_params.parallel_tool_calls,
                prompt_cache_retention=create_params.prompt_cache_retention,
                temperature=create_params.temperature,
                tools=create_params.tools,
                top_logprobs=create_params.top_logprobs,
                top_p=create_params.top_p,
                truncation=create_params.truncation,
            )
            return self._adapt_response(response)
        except Exception as e:
            raise_llm_error_from_openai(e, backend="responses")

    def _process_output_item_done_event(
        self, event: ResponseOutputItemDoneEvent
    ) -> Iterator[LLMEvent]:
        if not isinstance(event.item, ResponseFunctionWebSearch):
            return
        output = ToolOutput(
            display=self._format_web_search(event.item),
            is_error=event.item.status == "failed",
        )
        result = ToolResult(output=output, call_id=event.item.id)
        yield LLMToolCompleted(tool_name="web_search", result=result)

    def _process_response_completed_event(
        self, event: ResponseCompletedEvent
    ) -> Iterator[LLMEvent]:
        tool_calls = self.adapter.parse_tool_calls(event.response)
        for call in tool_calls:
            yield LLMToolCallRequested(call=call)
        yield LLMResponseCompleted(
            response=LLMResponse(
                output=AssistantMessage(
                    content=event.response.output_text or "",
                    tool_calls=tool_calls,
                ),
                usage=self._adapt_usage(event.response),
            )
        )

    def _process_stream_event(self, event: ResponseStreamEvent) -> Iterator[LLMEvent]:
        if isinstance(event, ResponseTextDeltaEvent):
            yield LLMTextDelta(text=event.delta)
            return
        if isinstance(event, ResponseWebSearchCallInProgressEvent):
            call = ToolCall(tool_name="web_search", call_id=event.item_id, arguments={})
            yield LLMToolStarted(call=call)
            return
        if isinstance(event, ResponseOutputItemDoneEvent):
            yield from self._process_output_item_done_event(event)
            return
        if isinstance(event, ResponseCompletedEvent):
            yield from self._process_response_completed_event(event)

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        create_params = self._resolve_create_params(request)
        try:
            stream = await self.client.responses.create(
                input=create_params.input,
                model=create_params.model,
                parallel_tool_calls=create_params.parallel_tool_calls,
                prompt_cache_retention=create_params.prompt_cache_retention,
                stream=True,
                temperature=create_params.temperature,
                tools=create_params.tools,
                top_logprobs=create_params.top_logprobs,
                top_p=create_params.top_p,
                truncation=create_params.truncation,
            )
            async for event in stream:
                for processed_event in self._process_stream_event(event):
                    yield processed_event
        except Exception as e:
            raise_llm_error_from_openai(e, backend="responses")


class ResponsesDriverAdapter(
    LLMAdapter[ResponseInputParam, list[FunctionToolParam] | Omit, Response]
): ...
