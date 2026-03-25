from __future__ import annotations

from functools import singledispatch

from koda.llm.types import LLMEvent
from koda.llm.types import LLMResponseCompleted as CoreResponseCompleted
from koda.llm.types import LLMTextDelta as CoreTextDelta
from koda.llm.types import LLMThinkingDelta as CoreThinkingDelta
from koda.llm.types import LLMToolCallRequested as CoreToolCallRequested
from koda.llm.types import LLMToolCallResult as CoreToolCallResult
from koda.llm.types import LLMToolCompleted as CoreProviderToolCompleted
from koda.llm.types import LLMToolStarted as CoreProviderToolStarted
from koda_service.mappers.messages import map_assistant_message_to_contract_assistant_message
from koda_service.mappers.tools import (
    map_tool_call_to_contract_tool_call,
    map_tool_result_to_contract_tool_result,
)
from koda_service.types.events import (
    ProviderToolCompleted,
    ProviderToolStarted,
    ResponseCompleted,
    StreamEvent,
    TextDelta,
    ThinkingDelta,
    TokenUsage,
    ToolCallRequested,
    ToolCallResult,
)


class UnsupportedLLMEventTypeError(TypeError):
    def __init__(self, llm_event: LLMEvent) -> None:
        super().__init__(f"Unsupported LLM event type: {type(llm_event).__name__}")


@singledispatch
def map_llm_event_to_stream_event(llm_event: LLMEvent) -> StreamEvent:
    """Map LLM event to contract stream event."""
    raise UnsupportedLLMEventTypeError(llm_event)


# Core text streaming events
@map_llm_event_to_stream_event.register
def _(event: CoreTextDelta) -> StreamEvent:
    return TextDelta(text=event.text)


@map_llm_event_to_stream_event.register
def _(event: CoreThinkingDelta) -> StreamEvent:
    return ThinkingDelta(text=event.text)


# Core tool lifecycle events
@map_llm_event_to_stream_event.register
def _(event: CoreToolCallRequested) -> StreamEvent:
    return ToolCallRequested(call=map_tool_call_to_contract_tool_call(event.call))


@map_llm_event_to_stream_event.register
def _(event: CoreToolCallResult) -> StreamEvent:
    return ToolCallResult(
        tool_name=event.tool_name,
        result=map_tool_result_to_contract_tool_result(event.result),
    )


@map_llm_event_to_stream_event.register
def _(event: CoreProviderToolStarted) -> StreamEvent:
    return ProviderToolStarted(call=map_tool_call_to_contract_tool_call(event.call))


@map_llm_event_to_stream_event.register
def _(event: CoreProviderToolCompleted) -> StreamEvent:
    return ProviderToolCompleted(
        tool_name=event.tool_name,
        result=map_tool_result_to_contract_tool_result(event.result),
    )


@map_llm_event_to_stream_event.register
def _(event: CoreResponseCompleted) -> StreamEvent:
    usage = event.response.usage
    output = map_assistant_message_to_contract_assistant_message(event.response.output)
    if usage is None:
        return ResponseCompleted(output=output)
    return ResponseCompleted(
        output=output,
        usage=TokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.cached_tokens,
            total_tokens=usage.total_tokens,
        ),
    )
