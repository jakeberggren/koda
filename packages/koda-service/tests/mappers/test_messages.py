import pytest

from koda.messages import AssistantMessage as CoreAssistantMessage
from koda.messages import ToolMessage as CoreToolMessage
from koda.messages import UserMessage as CoreUserMessage
from koda.tools import ToolCall as CoreToolCall
from koda.tools import ToolOutput as CoreToolOutput
from koda.tools import ToolResult as CoreToolResult
from koda_service.mappers import (
    map_message_to_contract_message,
    map_messages_to_contract_messages,
)
from koda_service.mappers.messages import UnsupportedCoreMessageTypeError
from koda_service.types import AssistantMessage, ToolMessage, UserMessage

EXPECTED_MESSAGE_COUNT = 2


def test_map_message_to_contract_message_maps_user_message() -> None:
    contract_message = map_message_to_contract_message(CoreUserMessage(content="Hello"))

    assert isinstance(contract_message, UserMessage)
    assert contract_message.content == "Hello"


def test_map_message_to_contract_message_maps_assistant_message() -> None:
    contract_message = map_message_to_contract_message(
        CoreAssistantMessage(
            content="Here you go",
            thinking_content="reasoning",
            tool_calls=[
                CoreToolCall(
                    tool_name="read_file",
                    arguments={"path": "README.md"},
                    call_id="call-123",
                )
            ],
        )
    )

    assert isinstance(contract_message, AssistantMessage)
    assert contract_message.content == "Here you go"
    assert contract_message.thinking_content == "reasoning"
    assert len(contract_message.tool_calls) == 1
    assert contract_message.tool_calls[0].tool_name == "read_file"


def test_map_message_to_contract_message_maps_tool_message() -> None:
    contract_message = map_message_to_contract_message(
        CoreToolMessage(
            content="File contents",
            tool_name="read_file",
            tool_result=CoreToolResult(
                output=CoreToolOutput(content={"text": "hello"}),
                call_id="call-123",
            ),
        )
    )

    assert isinstance(contract_message, ToolMessage)
    assert contract_message.tool_name == "read_file"
    assert contract_message.tool_result.call_id == "call-123"
    assert contract_message.tool_result.output.content == {"text": "hello"}


def test_map_messages_to_contract_messages_maps_message_list() -> None:
    contract_messages = map_messages_to_contract_messages(
        [
            CoreUserMessage(content="Hi"),
            CoreAssistantMessage(content="Hello"),
        ]
    )

    assert len(contract_messages) == EXPECTED_MESSAGE_COUNT
    assert isinstance(contract_messages[0], UserMessage)
    assert isinstance(contract_messages[1], AssistantMessage)


def test_map_message_to_contract_message_raises_for_unsupported_type() -> None:
    with pytest.raises(UnsupportedCoreMessageTypeError):
        map_message_to_contract_message(object())
