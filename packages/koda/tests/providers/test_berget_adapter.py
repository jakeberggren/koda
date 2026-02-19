import json
from typing import cast

import pytest
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_message_custom_tool_call import (
    ChatCompletionMessageCustomToolCall,
    Custom,
)
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)
from pydantic import BaseModel

from koda.messages import AssistantMessage, SystemMessage, ToolMessage
from koda.providers.berget.adapter import BergetAIAdapter
from koda.providers.exceptions import InvalidToolCallArgumentsError, UnknownMessageTypeError
from koda.tools.base import ToolCall, ToolDefinition, ToolOutput, ToolResult


def test_adapt_assistant_includes_tool_calls() -> None:
    adapter = BergetAIAdapter()
    expected_tool_call_count = 2
    assistant = AssistantMessage(
        content="Let me check.",
        tool_calls=[
            ToolCall(tool_name="search", arguments={"q": "koda"}, call_id="call_1"),
            ToolCall(tool_name="read_file", arguments={"path": "README.md"}, call_id="call_2"),
        ],
    )

    items = adapter.adapt_messages([assistant])
    assert len(items) == 1

    assistant_item = cast("dict[str, object]", items[0])
    assert assistant_item["role"] == "assistant"
    assert assistant_item["content"] == "Let me check."
    tool_calls = cast("list[dict[str, object]]", assistant_item["tool_calls"])
    assert len(tool_calls) == expected_tool_call_count
    assert tool_calls[0]["id"] == "call_1"
    assert tool_calls[0]["type"] == "function"
    first_function = cast("dict[str, object]", tool_calls[0]["function"])
    assert first_function["name"] == "search"
    assert json.loads(cast("str", first_function["arguments"])) == {"q": "koda"}


def test_adapt_tool_message_includes_tool_error_metadata() -> None:
    adapter = BergetAIAdapter()
    tool_msg = ToolMessage(
        tool_name="some_tool",
        tool_result=ToolResult(
            output=ToolOutput(is_error=True, error_message="boom"),
            call_id="call_123",
        ),
    )

    items = adapter.adapt_messages([tool_msg])
    assert len(items) == 1

    item = cast("dict[str, object]", items[0])
    assert item["role"] == "tool"
    assert item["tool_call_id"] == "call_123"
    payload = json.loads(cast("str", item["content"]))
    assert payload == {"content": {}, "is_error": True, "error_message": "boom"}


def test_adapt_tool_message_omits_error_message_when_none() -> None:
    adapter = BergetAIAdapter()
    tool_msg = ToolMessage(
        tool_name="some_tool",
        tool_result=ToolResult(
            output=ToolOutput(content={"ok": True}),
            call_id="call_123",
        ),
    )

    items = adapter.adapt_messages([tool_msg])
    item = cast("dict[str, object]", items[0])
    payload = json.loads(cast("str", item["content"]))
    assert payload == {"content": {"ok": True}, "is_error": False}


def test_adapt_messages_raises_for_unknown_message_type() -> None:
    adapter = BergetAIAdapter()

    with pytest.raises(UnknownMessageTypeError):
        adapter.adapt_messages([SystemMessage(content="system prompt")])


def test_parse_tool_calls_parses_function_and_skips_custom() -> None:
    adapter = BergetAIAdapter()
    response = ChatCompletion.model_validate(
        {
            "id": "resp_1",
            "object": "chat.completion",
            "created": 0,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            ChatCompletionMessageFunctionToolCall(
                                id="call_1",
                                type="function",
                                function=Function(name="search", arguments='{"q":"koda"}'),
                            ),
                            ChatCompletionMessageCustomToolCall(
                                id="call_custom",
                                type="custom",
                                custom=Custom(name="custom_tool", input="raw"),
                            ),
                        ],
                    },
                },
            ],
        },
    )

    calls = adapter.parse_tool_calls(response)
    assert len(calls) == 1
    assert calls[0].tool_name == "search"
    assert calls[0].call_id == "call_1"
    assert calls[0].arguments == {"q": "koda"}


def test_parse_tool_calls_raises_when_arguments_not_object() -> None:
    adapter = BergetAIAdapter()
    response = ChatCompletion.model_validate(
        {
            "id": "resp_2",
            "object": "chat.completion",
            "created": 0,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            ChatCompletionMessageFunctionToolCall(
                                id="call_1",
                                type="function",
                                function=Function(name="search", arguments="[]"),
                            ),
                        ],
                    },
                },
            ],
        },
    )

    with pytest.raises(InvalidToolCallArgumentsError):
        adapter.parse_tool_calls(response)


def test_adapt_tools_simplifies_single_non_null_anyof() -> None:
    adapter = BergetAIAdapter()

    class OptionalParams(BaseModel):
        value: int | None = None

    tools = [
        ToolDefinition(
            name="opt_tool",
            description="optional value",
            parameters_model=OptionalParams,
        ),
    ]

    adapted = cast("list[dict[str, object]]", adapter.adapt_tools(tools))
    function_spec = cast("dict[str, object]", adapted[0]["function"])
    parameters = cast("dict[str, object]", function_spec["parameters"])
    properties = cast("dict[str, object]", parameters["properties"])
    value_schema = cast("dict[str, object]", properties["value"])
    assert "anyOf" not in value_schema
    assert value_schema["type"] == "integer"


def test_simplify_schema_preserves_multi_option_anyof_when_not_flattenable() -> None:
    adapter = BergetAIAdapter()
    expected_options = 2

    class UnionParams(BaseModel):
        value: int | str

    tools = [
        ToolDefinition(
            name="union_tool",
            description="union value",
            parameters_model=UnionParams,
        ),
    ]

    adapted = cast("list[dict[str, object]]", adapter.adapt_tools(tools))
    function_spec = cast("dict[str, object]", adapted[0]["function"])
    parameters = cast("dict[str, object]", function_spec["parameters"])
    properties = cast("dict[str, object]", parameters["properties"])
    value_schema = cast("dict[str, object]", properties["value"])
    any_of = cast("list[dict[str, object]]", value_schema["anyOf"])
    assert len(any_of) == expected_options


def test_adapt_tools_drops_schema_key() -> None:
    adapter = BergetAIAdapter()

    class RawSchemaParams(BaseModel):
        @classmethod
        def model_json_schema(cls, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {},
            }

    tools = [
        ToolDefinition(
            name="raw_schema_tool",
            description="raw schema",
            parameters_model=RawSchemaParams,
        ),
    ]

    adapted = cast("list[dict[str, object]]", adapter.adapt_tools(tools))
    function_spec = cast("dict[str, object]", adapted[0]["function"])
    parameters = cast("dict[str, object]", function_spec["parameters"])
    assert "$schema" not in parameters
