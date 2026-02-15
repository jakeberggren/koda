from __future__ import annotations

from functools import singledispatch

from koda.providers.events import ProviderEvent
from koda.providers.events import ProviderToolCompleted as CoreProviderToolCompleted
from koda.providers.events import ProviderToolStarted as CoreProviderToolStarted
from koda.providers.events import TextDelta as CoreTextDelta
from koda.providers.events import ToolCallRequested as CoreToolCallRequested
from koda.providers.events import ToolCallResult as CoreToolCallResult
from koda_api.mappers.tools import (
    map_tool_call_to_contract_tool_call,
    map_tool_result_to_contract_tool_result,
)
from koda_common.contracts import (
    ProviderToolCompleted,
    ProviderToolStarted,
    StreamEvent,
    TextDelta,
    ToolCallRequested,
    ToolCallResult,
)


class UnsupportedProviderEventTypeError(TypeError):
    def __init__(self, provider_event: ProviderEvent) -> None:
        super().__init__(f"Unsupported provider event type: {type(provider_event).__name__}")


@singledispatch
def map_provider_event_to_stream_event(provider_event: ProviderEvent) -> StreamEvent:
    """Map provider event to contract stream event."""
    raise UnsupportedProviderEventTypeError(provider_event)


# Core text streaming events
@map_provider_event_to_stream_event.register
def _(event: CoreTextDelta) -> StreamEvent:
    return TextDelta(text=event.text)


# Core tool lifecycle events
@map_provider_event_to_stream_event.register
def _(event: CoreToolCallRequested) -> StreamEvent:
    return ToolCallRequested(call=map_tool_call_to_contract_tool_call(event.call))


@map_provider_event_to_stream_event.register
def _(event: CoreToolCallResult) -> StreamEvent:
    return ToolCallResult(
        tool_name=event.tool_name,
        result=map_tool_result_to_contract_tool_result(event.result),
    )


@map_provider_event_to_stream_event.register
def _(event: CoreProviderToolStarted) -> StreamEvent:
    return ProviderToolStarted(call=map_tool_call_to_contract_tool_call(event.call))


@map_provider_event_to_stream_event.register
def _(event: CoreProviderToolCompleted) -> StreamEvent:
    return ProviderToolCompleted(
        tool_name=event.tool_name,
        result=map_tool_result_to_contract_tool_result(event.result),
    )
