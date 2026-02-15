import pytest

from koda.providers.events import ProviderToolCompleted as CoreProviderToolCompleted
from koda.providers.events import ProviderToolStarted as CoreProviderToolStarted
from koda.providers.events import TextDelta as CoreTextDelta
from koda.providers.events import ToolCallRequested as CoreToolCallRequested
from koda.providers.events import ToolCallResult as CoreToolCallResult
from koda.tools import ToolCall as CoreToolCall
from koda.tools import ToolOutput as CoreToolOutput
from koda.tools import ToolResult as CoreToolResult
from koda_api.mappers import map_provider_event_to_stream_event
from koda_api.mappers.events import UnsupportedProviderEventTypeError
from koda_common.contracts import (
    ProviderToolCompleted,
    ProviderToolStarted,
    TextDelta,
    ToolCallRequested,
    ToolCallResult,
)


def _make_core_tool_call() -> CoreToolCall:
    return CoreToolCall(tool_name="read_file", arguments={"path": "/tmp/a"}, call_id="c1")


def _make_core_tool_result() -> CoreToolResult:
    return CoreToolResult(call_id="c1", output=CoreToolOutput(display="ok"))


def test_map_provider_text_delta_event() -> None:
    mapped = map_provider_event_to_stream_event(CoreTextDelta(text="hi"))
    assert isinstance(mapped, TextDelta)
    assert mapped.text == "hi"


def test_map_provider_tool_call_requested_event() -> None:
    mapped = map_provider_event_to_stream_event(CoreToolCallRequested(call=_make_core_tool_call()))
    assert isinstance(mapped, ToolCallRequested)
    assert mapped.call.tool_name == "read_file"


def test_map_provider_tool_call_result_event() -> None:
    mapped = map_provider_event_to_stream_event(
        CoreToolCallResult(tool_name="read_file", result=_make_core_tool_result())
    )
    assert isinstance(mapped, ToolCallResult)
    assert mapped.result.call_id == "c1"


def test_map_provider_tool_started_event() -> None:
    mapped = map_provider_event_to_stream_event(
        CoreProviderToolStarted(call=_make_core_tool_call())
    )
    assert isinstance(mapped, ProviderToolStarted)
    assert mapped.call.call_id == "c1"


def test_map_provider_tool_completed_event() -> None:
    mapped = map_provider_event_to_stream_event(
        CoreProviderToolCompleted(tool_name="read_file", result=_make_core_tool_result())
    )
    assert isinstance(mapped, ProviderToolCompleted)
    assert mapped.result.output.display == "ok"


def test_map_provider_event_to_stream_event_unsupported_type() -> None:
    with pytest.raises(UnsupportedProviderEventTypeError):
        map_provider_event_to_stream_event(object())
