from functools import singledispatch

from koda.messages import AssistantMessage as CoreAssistantMessage
from koda.messages import Message as CoreMessage
from koda.messages import ToolMessage as CoreToolMessage
from koda.messages import UserMessage as CoreUserMessage
from koda_service.mappers.tools import (
    map_tool_call_to_contract_tool_call,
    map_tool_result_to_contract_tool_result,
)
from koda_service.types.messages import (
    AssistantMessage,
    Message,
    TokenUsage,
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
    return map_assistant_message_to_contract_assistant_message(core_message)


def map_assistant_message_to_contract_assistant_message(
    core_message: CoreAssistantMessage,
) -> AssistantMessage:
    """Map a core assistant message to the contract assistant message."""
    tool_calls = [map_tool_call_to_contract_tool_call(call) for call in core_message.tool_calls]
    return AssistantMessage(
        content=core_message.content,
        thinking_content=core_message.thinking_content,
        tool_calls=tool_calls,
        usage=(
            TokenUsage(
                input_tokens=core_message.usage.input_tokens,
                output_tokens=core_message.usage.output_tokens,
                cached_tokens=core_message.usage.cached_tokens,
                total_tokens=core_message.usage.total_tokens,
            )
            if core_message.usage is not None
            else None
        ),
    )


@map_message_to_contract_message.register
def _(core_message: CoreToolMessage) -> Message:
    tool_result = map_tool_result_to_contract_tool_result(core_message.tool_result)
    return ToolMessage(
        content=core_message.content,
        tool_name=core_message.tool_name,
        tool_result=tool_result,
    )


def map_messages_to_contract_messages(
    core_messages: list[CoreMessage],
) -> list[Message]:
    """Map core message list to contract message list."""
    return [map_message_to_contract_message(message) for message in core_messages]
