import pytest

from koda.messages import AssistantMessage as CoreAssistantMessage
from koda.messages import Message as CoreMessage
from koda.messages import ToolMessage as CoreToolMessage
from koda.messages import UserMessage as CoreUserMessage
from koda.tools import ToolCall as CoreToolCall
from koda.tools import ToolOutput as CoreToolOutput
from koda.tools import ToolResult as CoreToolResult
from koda_api.mappers import map_message_to_contract_message, map_messages_to_contract_messages
from koda_api.mappers.messages import UnsupportedCoreMessageTypeError
from koda_common.contracts import AssistantMessage, ToolMessage, UserMessage


def _make_core_tool_call() -> CoreToolCall:
    return CoreToolCall(tool_name="search", arguments={"q": "koda"}, call_id="c1")


def _make_core_tool_result() -> CoreToolResult:
    return CoreToolResult(call_id="c1", output=CoreToolOutput(display="done"))


def test_map_user_message_to_contract_message() -> None:
    mapped = map_message_to_contract_message(CoreUserMessage(content="hello"))
    assert isinstance(mapped, UserMessage)
    assert mapped.content == "hello"


def test_map_assistant_message_to_contract_message() -> None:
    mapped = map_message_to_contract_message(
        CoreAssistantMessage(
            content="Working...",
            thinking_content="Comparing approaches",
            tool_calls=[_make_core_tool_call()],
        )
    )
    assert isinstance(mapped, AssistantMessage)
    assert mapped.content == "Working..."
    assert mapped.thinking_content == "Comparing approaches"
    assert len(mapped.tool_calls) == 1
    assert mapped.tool_calls[0].tool_name == "search"


def test_map_tool_message_to_contract_message() -> None:
    mapped = map_message_to_contract_message(
        CoreToolMessage(tool_name="search", tool_result=_make_core_tool_result())
    )
    assert isinstance(mapped, ToolMessage)
    assert mapped.tool_name == "search"
    assert mapped.tool_result.call_id == "c1"


def test_map_messages_to_contract_messages() -> None:
    core_messages: list[CoreMessage] = [
        CoreUserMessage(content="hello"),
        CoreAssistantMessage(content="ok"),
    ]

    mapped = map_messages_to_contract_messages(core_messages)

    assert len(mapped) == 2  # noqa: PLR2004
    assert isinstance(mapped[0], UserMessage)
    assert isinstance(mapped[1], AssistantMessage)


def test_map_message_to_contract_message_unsupported_type() -> None:
    with pytest.raises(UnsupportedCoreMessageTypeError):
        map_message_to_contract_message(object())
