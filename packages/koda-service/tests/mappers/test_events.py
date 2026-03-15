import pytest

from koda.llm.types import (
    LLMTextDelta,
    LLMThinkingDelta,
    LLMToolCallRequested,
    LLMToolCallResult,
    LLMToolCompleted,
    LLMToolStarted,
)
from koda.tools import ToolCall as CoreToolCall
from koda.tools import ToolOutput as CoreToolOutput
from koda.tools import ToolResult as CoreToolResult
from koda_service.mappers.events import UnsupportedLLMEventTypeError, map_llm_event_to_stream_event
from koda_service.types import (
    ProviderToolCompleted,
    ProviderToolStarted,
    TextDelta,
    ThinkingDelta,
    ToolCallRequested,
    ToolCallResult,
)


def test_map_llm_event_to_stream_event_maps_text_delta() -> None:
    stream_event = map_llm_event_to_stream_event(LLMTextDelta(text="Hello"))

    assert isinstance(stream_event, TextDelta)
    assert stream_event.text == "Hello"


def test_map_llm_event_to_stream_event_maps_thinking_delta() -> None:
    stream_event = map_llm_event_to_stream_event(LLMThinkingDelta(text="thinking"))

    assert isinstance(stream_event, ThinkingDelta)
    assert stream_event.text == "thinking"


def test_map_llm_event_to_stream_event_maps_tool_call_requested() -> None:
    stream_event = map_llm_event_to_stream_event(
        LLMToolCallRequested(
            call=CoreToolCall(
                tool_name="read_file",
                arguments={"path": "README.md"},
                call_id="call-123",
            )
        )
    )

    assert isinstance(stream_event, ToolCallRequested)
    assert stream_event.call.tool_name == "read_file"


def test_map_llm_event_to_stream_event_maps_tool_call_result() -> None:
    stream_event = map_llm_event_to_stream_event(
        LLMToolCallResult(
            tool_name="read_file",
            result=CoreToolResult(
                output=CoreToolOutput(content={"text": "hello"}),
                call_id="call-123",
            ),
        )
    )

    assert isinstance(stream_event, ToolCallResult)
    assert stream_event.tool_name == "read_file"
    assert stream_event.result.call_id == "call-123"


def test_map_llm_event_to_stream_event_maps_provider_tool_started() -> None:
    stream_event = map_llm_event_to_stream_event(
        LLMToolStarted(
            call=CoreToolCall(
                tool_name="read_file",
                arguments={"path": "README.md"},
                call_id="call-123",
            )
        )
    )

    assert isinstance(stream_event, ProviderToolStarted)
    assert stream_event.call.call_id == "call-123"


def test_map_llm_event_to_stream_event_maps_provider_tool_completed() -> None:
    stream_event = map_llm_event_to_stream_event(
        LLMToolCompleted(
            tool_name="read_file",
            result=CoreToolResult(
                output=CoreToolOutput(content={"text": "hello"}),
                call_id="call-123",
            ),
        )
    )

    assert isinstance(stream_event, ProviderToolCompleted)
    assert stream_event.tool_name == "read_file"
    assert stream_event.result.output.content == {"text": "hello"}


def test_map_llm_event_to_stream_event_raises_for_unsupported_type() -> None:
    with pytest.raises(UnsupportedLLMEventTypeError):
        map_llm_event_to_stream_event(object())
