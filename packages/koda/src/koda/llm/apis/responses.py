from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal

import openai
from openai import AsyncOpenAI, Omit, OpenAIError, omit
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    Response,
    ResponseCompletedEvent,
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ResponseInputParam,
    ResponseOutputItemDoneEvent,
    ResponseReasoningSummaryPartAddedEvent,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ResponseWebSearchCallInProgressEvent,
    ToolParam,
    WebSearchToolParam,
)
from openai.types.responses.response_function_tool_call_param import (
    ResponseFunctionToolCallParam,
)
from openai.types.responses.response_function_web_search import ActionSearch
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputItemParam
from pydantic import BaseModel

from koda.llm import exceptions
from koda.llm.apis.credentials import resolve_api_key_credential
from koda.llm.protocols import LLM, LLMAdapter
from koda.llm.types import (
    LLMResponse,
    LLMResponseCompleted,
    LLMTextDelta,
    LLMThinkingDelta,
    LLMToolCallRequested,
    LLMToolCompleted,
    LLMToolStarted,
)
from koda.llm.utils import raise_llm_error_from_openai, resolve_openai_client
from koda.messages import AssistantMessage, TokenUsage, ToolMessage, UserMessage
from koda.tools import ToolCall, ToolOutput, ToolResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator, Sequence

    from openai.types.chat.completion_create_params import ReasoningEffort
    from openai.types.shared_params.reasoning import Reasoning

    from koda.llm import LLMEvent
    from koda.llm.apis.base import LLMApiContext
    from koda.llm.models import ThinkingOptionId
    from koda.llm.types import LLMRequest
    from koda.messages import Message
    from koda.tools import ToolDefinition


type OpenAIResponsesLLMAdapter = LLMAdapter[ResponseInputParam, list[ToolParam] | Omit, Response]

_OPENAI_REASONING_EFFORTS: dict[ThinkingOptionId, ReasoningEffort] = {
    "none": "none",
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "xhigh",
}


@dataclass(frozen=True, slots=True)
class OpenAIResponsesAPIConfig:
    """Runtime configuration for OpenAI's Responses API."""

    api_key: str
    base_url: str
    model: str
    backend: str = "openai-responses"
    web_search: bool = False
    extended_prompt_retention: bool = False
    prompt_cache_retention_supported: bool = True
    truncation_supported: bool = True
    store: bool | Omit = omit


class OpenAIResponsesAdapter(LLMAdapter[ResponseInputParam, list[ToolParam] | Omit, Response]):
    """Convert between Koda messages/tools/responses and OpenAI Responses types."""

    @staticmethod
    def _parse_tool_call_arguments(raw_arguments: str) -> dict[str, Any]:
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as error:
            raise exceptions.InvalidToolCallArgumentsError from error
        if not isinstance(arguments, dict):
            raise exceptions.InvalidToolCallArgumentsError
        return arguments

    @staticmethod
    def _to_provider_user_message(message: UserMessage) -> EasyInputMessageParam:
        return EasyInputMessageParam(role="user", content=message.content, type="message")

    @staticmethod
    def _to_provider_tool_message(message: ToolMessage) -> FunctionCallOutput:
        tool_output = message.tool_result.output
        output_data: dict[str, Any] = {
            "content": tool_output.content,
            "is_error": tool_output.is_error,
        }
        if tool_output.error_message:
            output_data["error_message"] = tool_output.error_message
        return FunctionCallOutput(
            call_id=message.tool_result.call_id,
            output=json.dumps(output_data),
            type="function_call_output",
        )

    @staticmethod
    def _to_provider_assistant_message(message: AssistantMessage) -> list[ResponseInputItemParam]:
        result: list[ResponseInputItemParam] = []
        if message.content or not message.tool_calls:
            result.append(
                EasyInputMessageParam(
                    role="assistant",
                    content=message.content,
                    type="message",
                )
            )
        result.extend(
            ResponseFunctionToolCallParam(
                type="function_call",
                name=tool_call.tool_name,
                arguments=json.dumps(tool_call.arguments),
                call_id=tool_call.call_id,
            )
            for tool_call in message.tool_calls
        )
        return result

    def to_provider_messages(self, messages: Sequence[Message]) -> ResponseInputParam:
        result: ResponseInputParam = []
        for message in messages:
            if isinstance(message, UserMessage):
                result.append(self._to_provider_user_message(message))
                continue
            if isinstance(message, ToolMessage):
                result.append(self._to_provider_tool_message(message))
                continue
            if isinstance(message, AssistantMessage):
                result.extend(self._to_provider_assistant_message(message))
                continue
            raise exceptions.UnknownMessageTypeError(type(message))
        return result

    @staticmethod
    def _to_provider_tool_definition(tool: ToolDefinition) -> FunctionToolParam:
        schema = openai.pydantic_function_tool(
            tool.parameters_model,
            name=tool.name,
            description=tool.description,
        )
        function = schema["function"]
        return FunctionToolParam(
            type="function",
            name=function["name"],
            description=function.get("description"),
            parameters=function["parameters"],
            strict=function.get("strict", True),
        )

    def to_provider_tools(self, tools: Sequence[ToolDefinition] | None) -> list[ToolParam] | Omit:
        if not tools:
            return omit
        return [self._to_provider_tool_definition(tool) for tool in tools]

    def _extract_tool_calls(self, response: Response) -> list[ToolCall]:
        if response.output is None:
            return []
        return [
            ToolCall(
                tool_name=output.name,
                arguments=self._parse_tool_call_arguments(output.arguments),
                call_id=output.call_id,
            )
            for output in response.output
            if isinstance(output, ResponseFunctionToolCall)
        ]

    @staticmethod
    def _adapt_usage(response: Response) -> TokenUsage | None:
        usage = response.usage
        if usage is None:
            return None
        return TokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.input_tokens_details.cached_tokens,
            total_tokens=usage.total_tokens,
        )

    def to_llm_response(self, response: Response) -> LLMResponse[AssistantMessage]:
        return LLMResponse(
            output=AssistantMessage(
                content=response.output_text if response.output is not None else "",
                tool_calls=self._extract_tool_calls(response),
            ),
            usage=self._adapt_usage(response),
        )


class OpenAIResponsesEventAdapter:
    """Convert OpenAI Responses streaming events into Koda LLM stream events."""

    @staticmethod
    def _parse_tool_call_arguments(raw_arguments: str) -> dict[str, Any]:
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as error:
            raise exceptions.InvalidToolCallArgumentsError from error
        if not isinstance(arguments, dict):
            raise exceptions.InvalidToolCallArgumentsError
        return arguments

    @staticmethod
    def _format_web_search(output: ResponseFunctionWebSearch) -> str | None:
        action = output.action
        if not isinstance(action, ActionSearch):
            return None
        return f'Searched for "{action.query}"'

    def _to_function_tool_call(self, output: ResponseFunctionToolCall) -> ToolCall:
        return ToolCall(
            tool_name=output.name,
            arguments=self._parse_tool_call_arguments(output.arguments),
            call_id=output.call_id,
        )

    def _events_from_output_item_done(
        self, event: ResponseOutputItemDoneEvent
    ) -> Iterator[LLMEvent]:
        if isinstance(event.item, ResponseFunctionToolCall):
            yield LLMToolCallRequested(call=self._to_function_tool_call(event.item))
            return
        if not isinstance(event.item, ResponseFunctionWebSearch):
            return
        output = ToolOutput(
            display=self._format_web_search(event.item),
            is_error=event.item.status == "failed",
        )
        result = ToolResult(output=output, call_id=event.item.id)
        yield LLMToolCompleted(tool_name="web_search", result=result)

    def to_llm_events(self, event: ResponseStreamEvent) -> Iterator[LLMEvent]:  # noqa: C901
        if isinstance(event, ResponseTextDeltaEvent):
            yield LLMTextDelta(text=event.delta)
        elif isinstance(event, ResponseReasoningSummaryPartAddedEvent):
            if event.summary_index > 0:
                yield LLMThinkingDelta(text="\n\n")
        elif isinstance(event, ResponseReasoningSummaryTextDeltaEvent):
            yield LLMThinkingDelta(text=event.delta)
        elif isinstance(event, ResponseWebSearchCallInProgressEvent):
            call = ToolCall(tool_name="web_search", call_id=event.item_id, arguments={})
            yield LLMToolStarted(call=call)
        elif isinstance(event, ResponseOutputItemDoneEvent):
            yield from self._events_from_output_item_done(event)


def _resolve_reasoning(reasoning: ThinkingOptionId) -> Reasoning:
    effort = _OPENAI_REASONING_EFFORTS[reasoning]
    return {"effort": effort, "summary": "auto"}


def _or_omit[T](value: T | None) -> T | Omit:
    return value if value is not None else omit


class OpenAIResponsesAPI(LLM):
    """Concrete LLM implementation backed by OpenAI's Responses API."""

    def __init__(
        self,
        config: OpenAIResponsesAPIConfig,
        *,
        client: AsyncOpenAI,
        adapter: OpenAIResponsesLLMAdapter,
        event_adapter: OpenAIResponsesEventAdapter,
    ) -> None:
        self.config = config
        self.client = client
        self.adapter = adapter
        self.event_adapter = event_adapter

    @classmethod
    async def from_context(cls, context: LLMApiContext) -> OpenAIResponsesAPI:
        """Create an OpenAI Responses API from a resolved model-catalog context."""
        capabilities = (
            context.provider.capabilities
            | context.connection.capabilities
            | context.model.capabilities
        )
        config = OpenAIResponsesAPIConfig(
            api_key=resolve_api_key_credential(context),
            base_url=context.connection.base_url,
            model=context.model.id,
            web_search=bool(capabilities.get("web_search", False)),
            extended_prompt_retention=bool(capabilities.get("extended_prompt_retention", False)),
        )
        client_factory = resolve_openai_client(context.settings)
        return cls(
            config,
            client=client_factory(api_key=config.api_key, base_url=config.base_url),
            adapter=OpenAIResponsesAdapter(),
            event_adapter=OpenAIResponsesEventAdapter(),
        )

    def _apply_model_features(self, request: LLMRequest) -> LLMRequest:
        resolved_options = replace(
            request.options,
            web_search=request.options.web_search and self.config.web_search,
            extended_prompt_retention=(
                request.options.extended_prompt_retention and self.config.extended_prompt_retention
            ),
        )
        return replace(request, options=resolved_options)

    def _resolve_prompt_cache_retention(
        self,
        *,
        extended_prompt_retention: bool,
    ) -> Literal["24h"] | Omit:
        if not self.config.prompt_cache_retention_supported:
            return omit
        return _or_omit("24h" if extended_prompt_retention else None)

    def _resolve_tools(self, request: LLMRequest) -> list[ToolParam] | Omit:
        adapted_tools = self.adapter.to_provider_tools(request.tools)
        if not request.options.web_search:
            return adapted_tools
        web_search_tool = WebSearchToolParam(type="web_search")
        if isinstance(adapted_tools, Omit):
            return [web_search_tool]
        return [*adapted_tools, web_search_tool]

    def _resolve_truncation(self, request: LLMRequest) -> Literal["auto", "disabled"] | Omit:
        if not self.config.truncation_supported:
            return omit
        return _or_omit(request.options.truncation)

    async def generate(self, request: LLMRequest) -> LLMResponse[AssistantMessage]:
        resolved_request = self._apply_model_features(request)
        try:
            response = await self.client.responses.create(
                input=self.adapter.to_provider_messages(resolved_request.messages),
                instructions=_or_omit(resolved_request.instructions),
                max_output_tokens=_or_omit(resolved_request.options.max_output_tokens),
                max_tool_calls=_or_omit(resolved_request.options.max_tool_calls),
                model=self.config.model,
                parallel_tool_calls=resolved_request.options.parallel_tool_calls,
                prompt_cache_retention=self._resolve_prompt_cache_retention(
                    extended_prompt_retention=resolved_request.options.extended_prompt_retention
                ),
                reasoning=_resolve_reasoning(resolved_request.options.thinking),
                store=self.config.store,
                temperature=_or_omit(resolved_request.options.temperature),
                tools=self._resolve_tools(resolved_request),
                top_logprobs=_or_omit(resolved_request.options.top_logprobs),
                top_p=_or_omit(resolved_request.options.top_p),
                truncation=self._resolve_truncation(resolved_request),
            )
        except OpenAIError as error:
            raise_llm_error_from_openai(error, backend=self.config.backend)
        return self.adapter.to_llm_response(response)

    async def generate_stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        resolved_request = self._apply_model_features(request)
        try:
            stream = await self.client.responses.create(
                input=self.adapter.to_provider_messages(resolved_request.messages),
                instructions=_or_omit(resolved_request.instructions),
                max_output_tokens=_or_omit(resolved_request.options.max_output_tokens),
                max_tool_calls=_or_omit(resolved_request.options.max_tool_calls),
                model=self.config.model,
                parallel_tool_calls=resolved_request.options.parallel_tool_calls,
                prompt_cache_retention=self._resolve_prompt_cache_retention(
                    extended_prompt_retention=resolved_request.options.extended_prompt_retention
                ),
                reasoning=_resolve_reasoning(resolved_request.options.thinking),
                store=self.config.store,
                stream=True,
                temperature=_or_omit(resolved_request.options.temperature),
                tools=self._resolve_tools(resolved_request),
                top_logprobs=_or_omit(resolved_request.options.top_logprobs),
                top_p=_or_omit(resolved_request.options.top_p),
                truncation=self._resolve_truncation(resolved_request),
            )
            async for event in stream:
                if isinstance(event, ResponseCompletedEvent):
                    yield LLMResponseCompleted(
                        response=self.adapter.to_llm_response(event.response)
                    )
                    continue
                for processed_event in self.event_adapter.to_llm_events(event):
                    yield processed_event
        except OpenAIError as error:
            raise_llm_error_from_openai(error, backend=self.config.backend)

    async def generate_structured[T: BaseModel](
        self,
        request: LLMRequest,
        schema: type[T],
    ) -> LLMResponse[T]:
        _ = request, schema
        raise exceptions.StructuredOutputNotSupportedError
