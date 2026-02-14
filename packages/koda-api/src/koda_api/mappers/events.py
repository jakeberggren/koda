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


def map_provider_event_to_stream_event(provider_event: ProviderEvent) -> StreamEvent:  # noqa: C901 - allow complex
    """Map provider event to contract stream event."""
    if isinstance(provider_event, CoreTextDelta):
        return TextDelta(text=provider_event.text)
    if isinstance(provider_event, CoreToolCallRequested):
        return ToolCallRequested(call=map_tool_call_to_contract_tool_call(provider_event.call))
    if isinstance(provider_event, CoreToolCallResult):
        return ToolCallResult(
            tool_name=provider_event.tool_name,
            result=map_tool_result_to_contract_tool_result(provider_event.result),
        )
    if isinstance(provider_event, CoreProviderToolStarted):
        return ProviderToolStarted(call=map_tool_call_to_contract_tool_call(provider_event.call))
    if isinstance(provider_event, CoreProviderToolCompleted):
        return ProviderToolCompleted(
            tool_name=provider_event.tool_name,
            result=map_tool_result_to_contract_tool_result(provider_event.result),
        )
    raise UnsupportedProviderEventTypeError(provider_event)
