# ruff: noqa: S101

import json
from typing import cast

from openai.types.responses.response_input_param import FunctionCallOutput

from koda.core import message
from koda.providers.openai.adapter import OpenAIAdapter
from koda.tools.base import ToolResult


def test_adapt_messages_includes_tool_error_metadata() -> None:
    adapter = OpenAIAdapter()

    tool_msg = message.ToolMessage(
        tool_name="some_tool",
        call_id="call_123",
        result=ToolResult(
            content=None,
            is_error=True,
            error_message="boom",
            call_id="call_123",
        ),
    )

    items = adapter.adapt_messages([tool_msg])
    assert len(items) == 1

    item = cast(FunctionCallOutput, items[0])
    assert item["type"] == "function_call_output"
    assert item["call_id"] == "call_123"

    payload = json.loads(cast(str, item["output"]))
    assert payload == {"content": None, "is_error": True, "error_message": "boom"}


def test_adapt_messages_omits_error_message_when_none() -> None:
    adapter = OpenAIAdapter()

    tool_msg = message.ToolMessage(
        tool_name="some_tool",
        call_id="call_123",
        result=ToolResult(
            content={"ok": True}, is_error=False, error_message=None, call_id="call_123"
        ),
    )

    items = adapter.adapt_messages([tool_msg])
    item = cast(FunctionCallOutput, items[0])
    payload = json.loads(cast(str, item["output"]))

    assert payload == {"content": {"ok": True}, "is_error": False}
