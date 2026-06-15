from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from openai.types.responses import (
    Response,
    ResponseCompletedEvent,
    ResponseFunctionToolCall,
    ResponseOutputItemDoneEvent,
    ResponseReasoningSummaryPartAddedEvent,
)

from koda.llm.apis.responses import (
    OpenAIResponsesAdapter,
    OpenAIResponsesAPI,
    OpenAIResponsesAPIConfig,
    OpenAIResponsesEventAdapter,
)
from koda.llm.types import (
    LLMRequest,
    LLMResponseCompleted,
    LLMThinkingDelta,
    LLMToolCallRequested,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from openai import AsyncOpenAI


_EXPECTED_EVENT_COUNT = 2


class _FakeResponsesAPI:
    def __init__(self, events: Sequence[object]) -> None:
        self._events = events

    async def create(self, **_kwargs: object) -> AsyncIterator[object]:
        async def _stream() -> AsyncIterator[object]:
            for event in self._events:
                yield event

        return _stream()


class _FakeClient:
    def __init__(self, events: Sequence[object]) -> None:
        self.responses = _FakeResponsesAPI(events)


def _response_with_tool_call(tool_call: ResponseFunctionToolCall) -> Response:
    return Response.model_validate(
        {
            "id": "resp_1",
            "created_at": 0,
            "model": "gpt-5.2",
            "object": "response",
            "output": [tool_call],
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "top_p": 1.0,
            "background": False,
            "status": "completed",
            "text": {"format": {"type": "text"}},
            "truncation": "disabled",
            "usage": None,
        }
    )


def _api(events: Sequence[object]) -> OpenAIResponsesAPI:
    return OpenAIResponsesAPI(
        OpenAIResponsesAPIConfig(
            api_key="test-key", base_url="https://api.openai.com/v1", model="gpt-5.2"
        ),
        client=cast("AsyncOpenAI", _FakeClient(events)),
        adapter=OpenAIResponsesAdapter(),
        event_adapter=OpenAIResponsesEventAdapter(),
    )


@pytest.mark.asyncio
async def test_generate_stream_emits_function_tool_call_once() -> None:
    tool_call = ResponseFunctionToolCall.model_validate(
        {
            "arguments": '{"path": "foo.py"}',
            "call_id": "call_1",
            "name": "read_file",
            "type": "function_call",
            "id": "fc_1",
            "status": "completed",
        }
    )
    completed_response = _response_with_tool_call(tool_call)
    events = [
        ResponseOutputItemDoneEvent.model_validate(
            {
                "item": tool_call.model_dump(mode="json"),
                "output_index": 0,
                "sequence_number": 0,
                "type": "response.output_item.done",
            }
        ),
        ResponseCompletedEvent.model_validate(
            {
                "response": completed_response.model_dump(mode="json"),
                "sequence_number": 1,
                "type": "response.completed",
            }
        ),
    ]

    streamed_events = [
        event async for event in _api(events).generate_stream(LLMRequest(messages=[]))
    ]

    assert len(streamed_events) == _EXPECTED_EVENT_COUNT
    assert isinstance(streamed_events[0], LLMToolCallRequested)
    assert streamed_events[0].call.tool_name == "read_file"
    assert streamed_events[0].call.call_id == "call_1"
    assert streamed_events[0].call.arguments == {"path": "foo.py"}
    assert isinstance(streamed_events[1], LLMResponseCompleted)


def test_to_llm_events_separates_reasoning_summary_parts() -> None:
    adapter = OpenAIResponsesEventAdapter()
    first_part = ResponseReasoningSummaryPartAddedEvent.model_validate(
        {
            "item_id": "rs_1",
            "output_index": 0,
            "part": {"text": "", "type": "summary_text"},
            "sequence_number": 0,
            "summary_index": 0,
            "type": "response.reasoning_summary_part.added",
        }
    )
    second_part = ResponseReasoningSummaryPartAddedEvent.model_validate(
        {
            "item_id": "rs_1",
            "output_index": 0,
            "part": {"text": "", "type": "summary_text"},
            "sequence_number": 1,
            "summary_index": 1,
            "type": "response.reasoning_summary_part.added",
        }
    )

    assert list(adapter.to_llm_events(first_part)) == []
    assert list(adapter.to_llm_events(second_part)) == [LLMThinkingDelta(text="\n\n")]
