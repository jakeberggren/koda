from functools import singledispatch

from koda.messages import AssistantMessage as CoreAssistantMessage
from koda.messages import Message as CoreMessage
from koda.messages import ToolMessage as CoreToolMessage
from koda.messages import UserMessage as CoreUserMessage
from koda_api.mappers.tools import (
    map_tool_call_to_contract_tool_call,
    map_tool_result_to_contract_tool_result,
)
from koda_common.contracts import (
    AssistantMessage,
    Message,
    ToolMessage,
    UserMessage,
)


class UnsupportedCoreMessageTypeError(TypeError):
    def __init__(self, core_message: CoreMessage) -> None:
        super().__init__(f"Unsupported message type: {type(core_message).__name__}")


@singledispatch
def map_message_to_contract_message(core_message: CoreMessage) -> Message:
    """Map core message to contract message."""
    raise UnsupportedCoreMessageTypeError(core_message)


# Core text messages
@map_message_to_contract_message.register
def _(core_message: CoreUserMessage) -> Message:
    return UserMessage(content=core_message.content)


# Core assistant/tool messages
@map_message_to_contract_message.register
def _(core_message: CoreAssistantMessage) -> Message:
    tool_calls = [map_tool_call_to_contract_tool_call(call) for call in core_message.tool_calls]
    return AssistantMessage(
        content=core_message.content,
        thinking_content=core_message.thinking_content,
        tool_calls=tool_calls,
    )


@map_message_to_contract_message.register
def _(core_message: CoreToolMessage) -> Message:
    tool_result = map_tool_result_to_contract_tool_result(core_message.tool_result)
    return ToolMessage(
        content=core_message.content,
        tool_name=core_message.tool_name,
        tool_result=tool_result,
    )


def map_messages_to_contract_messages(core_messages: list[CoreMessage]) -> list[Message]:
    """Map core message list to contract message list."""
    return [map_message_to_contract_message(message) for message in core_messages]
