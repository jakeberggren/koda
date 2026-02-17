from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from openai import Omit, omit
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_assistant_message_param import (
    ChatCompletionAssistantMessageParam,
)
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion_tool_message_param import ChatCompletionToolMessageParam
from openai.types.chat.chat_completion_tool_union_param import ChatCompletionToolUnionParam
from openai.types.chat.chat_completion_user_message_param import ChatCompletionUserMessageParam

from koda.messages import AssistantMessage, Message, ToolMessage, UserMessage
from koda.providers.base import ProviderAdapter
from koda.providers.exceptions import UnknownMessageTypeError
from koda.tools import ToolCall, ToolDefinition

if TYPE_CHECKING:
    from collections.abc import Sequence


class InvalidToolCallArgumentsError(TypeError):
    def __init__(self) -> None:
        super().__init__("Tool call arguments must decode to a JSON object")


class BergetAIAdapter(
    ProviderAdapter[
        list[ChatCompletionMessageParam],
        list[ChatCompletionToolUnionParam] | Omit,
        ChatCompletion,
    ]
):
    """Adapter for converting to/from Berget's chat completions API format."""

    @staticmethod
    def _adapt_user_message(message: UserMessage) -> ChatCompletionUserMessageParam:
        """Convert an internal user message to chat completion format."""
        return ChatCompletionUserMessageParam(role="user", content=message.content)

    @staticmethod
    def _adapt_assistant_message(message: AssistantMessage) -> ChatCompletionAssistantMessageParam:
        """Convert an internal assistant message to chat completion format."""
        # Tool calls are represented by provider events and routed back as ToolMessage.
        return ChatCompletionAssistantMessageParam(role="assistant", content=message.content)

    @staticmethod
    def _serialize_tool_output(message: ToolMessage) -> str:
        """Serialize tool output payload as JSON for tool-role messages."""
        tool_output = message.tool_result.output
        payload: dict[str, Any] = {
            "content": tool_output.content,
            "is_error": tool_output.is_error,
        }
        if tool_output.error_message:
            payload["error_message"] = tool_output.error_message
        return json.dumps(payload)

    def _adapt_tool_message(self, message: ToolMessage) -> ChatCompletionToolMessageParam:
        """Convert an internal tool message to chat completion format."""
        return ChatCompletionToolMessageParam(
            role="tool",
            tool_call_id=message.tool_result.call_id,
            content=self._serialize_tool_output(message),
        )

    def adapt_messages(self, messages: Sequence[Message]) -> list[ChatCompletionMessageParam]:
        """Convert internal messages to provider chat completion messages."""
        result: list[ChatCompletionMessageParam] = []
        for message in messages:
            if isinstance(message, ToolMessage):
                result.append(self._adapt_tool_message(message))
                continue
            if isinstance(message, UserMessage):
                result.append(self._adapt_user_message(message))
                continue
            if isinstance(message, AssistantMessage):
                result.append(self._adapt_assistant_message(message))
                continue
            raise UnknownMessageTypeError(type(message))
        return result

    @staticmethod
    def _remove_null_type_from_anyof(options: list[Any]) -> list[Any]:
        """Drop explicit `null` branches from an `anyOf` options list."""
        return [
            option
            for option in options
            if not (isinstance(option, dict) and option.get("type") == "null")
        ]

    def _merge_single_anyof_object(
        self,
        result: dict[str, Any],
        options: list[Any],
    ) -> bool:
        """Flatten a single-object `anyOf` branch into the current schema node."""
        if len(options) != 1 or not isinstance(options[0], dict):
            return False
        inner = self._simplify_schema(options[0])
        if not isinstance(inner, dict):
            return False
        for inner_key, inner_value in inner.items():
            if inner_key not in result:
                result[inner_key] = inner_value
        return True

    def _simplify_schema_dict(self, value: dict[str, Any]) -> dict[str, Any]:
        """Simplify a schema object recursively for provider compatibility."""
        result: dict[str, Any] = {}
        for key, raw in value.items():
            # Relax strict Pydantic/OpenAI schema features that some providers reject.
            if key == "$schema":
                continue
            if key == "anyOf" and isinstance(raw, list):
                non_null = self._remove_null_type_from_anyof(raw)
                if self._merge_single_anyof_object(result, non_null):
                    continue
                result[key] = self._simplify_schema(non_null if non_null else raw)
                continue
            result[key] = self._simplify_schema(raw)
        return result

    def _simplify_schema(self, value: Any) -> Any:
        """Simplify JSON Schema for broader provider compatibility."""
        if isinstance(value, list):
            return [self._simplify_schema(item) for item in value]
        if isinstance(value, dict):
            return self._simplify_schema_dict(value)
        return value

    def _adapt_tool(self, tool: ToolDefinition) -> ChatCompletionToolUnionParam:
        """Convert a tool definition into the provider tool schema."""
        schema = self._simplify_schema(tool.parameters_model.model_json_schema())
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "strict": True,
                "parameters": schema,
            },
        }

    def adapt_tools(
        self,
        tools: list[ToolDefinition] | None,
    ) -> list[ChatCompletionToolUnionParam] | Omit:
        """Convert tool definitions or omit the field when none are provided."""
        if not tools:
            return omit
        return [self._adapt_tool(tool) for tool in tools]

    def parse_tool_calls(self, response: ChatCompletion) -> list[ToolCall]:
        """Extract function-style tool calls from a completion response."""
        calls: list[ToolCall] = []
        for choice in response.choices:
            for tool_call in choice.message.tool_calls or ():
                if not isinstance(tool_call, ChatCompletionMessageFunctionToolCall):
                    continue
                parsed_arguments = json.loads(tool_call.function.arguments)
                if not isinstance(parsed_arguments, dict):
                    raise InvalidToolCallArgumentsError
                calls.append(
                    ToolCall(
                        tool_name=tool_call.function.name,
                        arguments=parsed_arguments,
                        call_id=tool_call.id,
                    ),
                )
        return calls
