from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pytest
from anthropic.lib.streaming import MessageStreamEvent
from anthropic.types import Message
from pydantic import TypeAdapter

from koda.llm.apis.messages import (
    AnthropicMessagesAdapter,
    AnthropicMessagesAPI,
    AnthropicMessagesAPIConfig,
    AnthropicMessagesEventAdapter,
)
from koda.llm.types import (
    LLMRequest,
    LLMRequestOptions,
    LLMResponseCompleted,
    LLMThinkingDelta,
    LLMToolCallRequested,
)
from koda.messages import ToolMessage
from koda.tools import ToolOutput, ToolResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from anthropic import AsyncAnthropic


def _stream_event(data: object) -> MessageStreamEvent:
    return TypeAdapter(MessageStreamEvent).validate_python(data)


class _FakeMessagesAPI:
    def __init__(
        self,
        stream_message: Message | None = None,
        stream_events: list[object] | None = None,
    ) -> None:
        self.create_kwargs: dict[str, Any] | None = None
        self.stream_kwargs: dict[str, Any] | None = None
        self.stream_message = stream_message
        self.stream_events = stream_events or []

    async def create(self, **kwargs: Any) -> Message:
        self.create_kwargs = kwargs
        return Message.model_validate(
            {
                "id": "msg_1",
                "content": [],
                "model": kwargs["model"],
                "role": "assistant",
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "type": "message",
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                },
            }
        )

    def stream(self, **kwargs: Any) -> _FakeMessageStream:
        self.stream_kwargs = kwargs
        if self.stream_message is None:
            raise AssertionError("stream_message must be set before streaming")
        return _FakeMessageStream(self.stream_message, self.stream_events)


class _FakeClient:
    def __init__(
        self,
        stream_message: Message | None = None,
        stream_events: list[object] | None = None,
    ) -> None:
        self.messages = _FakeMessagesAPI(stream_message, stream_events)


class _FakeMessageStream:
    def __init__(self, final_message: Message, events: list[object]) -> None:
        self.final_message = final_message
        self.events = events

    async def __aenter__(self) -> _FakeMessageStream:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def __aiter__(self) -> AsyncIterator[object]:
        return self._events()

    async def _events(self) -> AsyncIterator[object]:
        for event in self.events:
            yield event

    async def get_final_message(self) -> Message:
        return self.final_message


def _message_with_tool_call() -> Message:
    return Message.model_validate(
        {
            "id": "msg_1",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "read_file",
                    "input": {"path": "pyproject.toml"},
                }
            ],
            "model": "claude-sonnet-4-6",
            "role": "assistant",
            "stop_reason": "tool_use",
            "stop_sequence": None,
            "type": "message",
            "usage": {
                "input_tokens": 1,
                "output_tokens": 1,
            },
        }
    )


def _provider(
    client: _FakeClient,
    *,
    thinking_budget_tokens: int | None = None,
) -> AnthropicMessagesAPI:
    return AnthropicMessagesAPI(
        AnthropicMessagesAPIConfig(
            api_key="test-key",
            base_url="https://api.anthropic.com",
            model="claude-sonnet-4-6",
            max_output_tokens=1024,
            thinking_budget_tokens=thinking_budget_tokens,
        ),
        client=cast("AsyncAnthropic", client),
        adapter=AnthropicMessagesAdapter(),
        event_adapter=AnthropicMessagesEventAdapter(),
    )


@pytest.mark.asyncio
async def test_anthropic_tool_result_sends_structured_content_not_display() -> None:
    fake_client = _FakeClient()
    provider = _provider(fake_client)
    request = LLMRequest(
        messages=[
            ToolMessage(
                tool_name="read_file",
                tool_result=ToolResult(
                    call_id="toolu_1",
                    output=ToolOutput(
                        content={"text": '[project]\nname = "koda"', "encoding": "utf-8"},
                        display="Read 2 lines",
                    ),
                ),
            )
        ]
    )

    await provider.generate(request)

    create_kwargs = fake_client.messages.create_kwargs
    assert create_kwargs is not None
    messages = create_kwargs["messages"]
    assert isinstance(messages, list)
    message = messages[0]
    assert isinstance(message, dict)
    assert message["role"] == "user"
    content = message["content"]
    assert isinstance(content, list)
    tool_result = content[0]
    assert isinstance(tool_result, dict)
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "toolu_1"
    payload = json.loads(tool_result["content"])
    assert payload == {
        "content": {"text": '[project]\nname = "koda"', "encoding": "utf-8"},
        "is_error": False,
    }


@pytest.mark.asyncio
async def test_anthropic_thinking_requests_summarized_display() -> None:
    fake_client = _FakeClient()
    provider = _provider(fake_client)

    await provider.generate(
        LLMRequest(
            messages=[],
            options=LLMRequestOptions(thinking="high"),
        )
    )

    create_kwargs = fake_client.messages.create_kwargs
    assert create_kwargs is not None
    assert create_kwargs["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert create_kwargs["output_config"] == {"effort": "high"}


@pytest.mark.asyncio
async def test_anthropic_extended_thinking_budget_is_less_than_max_tokens() -> None:
    fake_client = _FakeClient()
    provider = _provider(fake_client, thinking_budget_tokens=4096)

    await provider.generate(
        LLMRequest(
            messages=[],
            options=LLMRequestOptions(thinking="enabled", max_output_tokens=1024),
        )
    )

    create_kwargs = fake_client.messages.create_kwargs
    assert create_kwargs is not None
    assert create_kwargs["max_tokens"] == 1024
    assert create_kwargs["thinking"] == {
        "type": "enabled",
        "budget_tokens": 1023,
        "display": "summarized",
    }


@pytest.mark.asyncio
async def test_generate_stream_emits_thinking_delta() -> None:
    provider = _provider(
        _FakeClient(
            stream_message=_message_with_tool_call(),
            stream_events=[
                _stream_event(
                    {
                        "type": "thinking",
                        "thinking": "I should inspect the file.",
                        "snapshot": "I should inspect the file.",
                    }
                )
            ],
        )
    )

    events = [
        event
        async for event in provider.generate_stream(
            LLMRequest(messages=[], options=LLMRequestOptions(thinking="high"))
        )
    ]

    assert isinstance(events[0], LLMThinkingDelta)
    assert events[0].text == "I should inspect the file."


@pytest.mark.asyncio
async def test_generate_stream_emits_tool_call_from_final_response() -> None:
    provider = _provider(_FakeClient(stream_message=_message_with_tool_call()))

    events = [event async for event in provider.generate_stream(LLMRequest(messages=[]))]

    assert len(events) == 2
    assert isinstance(events[0], LLMToolCallRequested)
    assert events[0].call.tool_name == "read_file"
    assert events[0].call.call_id == "toolu_1"
    assert events[0].call.arguments == {"path": "pyproject.toml"}
    assert isinstance(events[1], LLMResponseCompleted)
    assert events[1].response.output.tool_calls == [events[0].call]
