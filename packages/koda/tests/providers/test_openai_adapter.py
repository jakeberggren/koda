import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall

from koda.messages import AssistantMessage, ToolMessage
from koda.providers.exceptions import InvalidToolCallArgumentsError
from koda.providers.openai.adapter import OpenAIAdapter
from koda.tools.base import ToolCall, ToolOutput, ToolResult

if TYPE_CHECKING:
    from openai.types.responses import Response
    from openai.types.responses.response_input_param import FunctionCallOutput


def test_adapt_messages_includes_tool_error_metadata() -> None:
    adapter = OpenAIAdapter()

    tool_msg = ToolMessage(
        tool_name="some_tool",
        tool_result=ToolResult(
            output=ToolOutput(
                is_error=True,
                error_message="boom",
            ),
            call_id="call_123",
        ),
    )

    items = adapter.adapt_messages([tool_msg])
    assert len(items) == 1

    item = cast("FunctionCallOutput", items[0])
    assert item["type"] == "function_call_output"
    assert item["call_id"] == "call_123"

    payload = json.loads(cast("str", item["output"]))
    assert payload == {"content": {}, "is_error": True, "error_message": "boom"}


def test_adapt_messages_omits_error_message_when_none() -> None:
    adapter = OpenAIAdapter()

    tool_msg = ToolMessage(
        tool_name="some_tool",
        tool_result=ToolResult(
            output=ToolOutput(content={"ok": True}),
            call_id="call_123",
        ),
    )

    items = adapter.adapt_messages([tool_msg])
    item = cast("FunctionCallOutput", items[0])
    payload = json.loads(cast("str", item["output"]))

    assert payload == {"content": {"ok": True}, "is_error": False}


def test_adapt_assistant_tool_calls_to_function_call_items() -> None:
    adapter = OpenAIAdapter()
    expected_item_count = 2
    assistant = AssistantMessage(
        content="",
        tool_calls=[
            ToolCall(tool_name="search", arguments={"q": "koda"}, call_id="call_1"),
            ToolCall(tool_name="read_file", arguments={"path": "README.md"}, call_id="call_2"),
        ],
    )

    items = adapter.adapt_messages([assistant])
    assert len(items) == expected_item_count

    first = cast("dict[str, object]", items[0])
    second = cast("dict[str, object]", items[1])
    assert first["type"] == "function_call"
    assert first["name"] == "search"
    assert first["call_id"] == "call_1"
    assert json.loads(cast("str", first["arguments"])) == {"q": "koda"}
    assert second["type"] == "function_call"
    assert second["name"] == "read_file"
    assert second["call_id"] == "call_2"
    assert json.loads(cast("str", second["arguments"])) == {"path": "README.md"}


def test_adapt_assistant_text_and_tool_calls_preserves_order() -> None:
    adapter = OpenAIAdapter()
    expected_item_count = 2
    assistant = AssistantMessage(
        content="I'll call a tool.",
        tool_calls=[ToolCall(tool_name="search", arguments={"q": "latest"}, call_id="call_3")],
    )

    items = adapter.adapt_messages([assistant])
    assert len(items) == expected_item_count

    message_item = cast("dict[str, object]", items[0])
    tool_call_item = cast("dict[str, object]", items[1])
    assert message_item["type"] == "message"
    assert message_item["role"] == "assistant"
    assert message_item["content"] == "I'll call a tool."
    assert tool_call_item["type"] == "function_call"
    assert tool_call_item["call_id"] == "call_3"


def test_parse_tool_calls_parses_function_calls() -> None:
    adapter = OpenAIAdapter()
    response = cast(
        "Response",
        SimpleNamespace(
            output=[
                ResponseFunctionToolCall(
                    type="function_call",
                    name="search",
                    arguments='{"q":"koda"}',
                    call_id="call_1",
                ),
            ],
        ),
    )

    calls = adapter.parse_tool_calls(response)
    assert len(calls) == 1
    assert calls[0].tool_name == "search"
    assert calls[0].arguments == {"q": "koda"}
    assert calls[0].call_id == "call_1"


def test_parse_tool_calls_ignores_non_function_items() -> None:
    adapter = OpenAIAdapter()
    response = cast(
        "Response",
        SimpleNamespace(
            output=[
                object(),
                ResponseFunctionToolCall(
                    type="function_call",
                    name="search",
                    arguments='{"q":"koda"}',
                    call_id="call_1",
                ),
            ],
        ),
    )

    calls = adapter.parse_tool_calls(response)
    assert len(calls) == 1
    assert calls[0].tool_name == "search"


def test_parse_tool_calls_raises_when_arguments_not_object() -> None:
    adapter = OpenAIAdapter()
    response = cast(
        "Response",
        SimpleNamespace(
            output=[
                ResponseFunctionToolCall(
                    type="function_call",
                    name="search",
                    arguments="[]",
                    call_id="call_1",
                ),
            ],
        ),
    )

    with pytest.raises(InvalidToolCallArgumentsError):
        adapter.parse_tool_calls(response)
