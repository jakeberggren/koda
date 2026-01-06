import json
from typing import Any

import openai
from openai import Omit, omit
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    Response,
    ResponseFunctionToolCall,
    ResponseInputParam,
)
from openai.types.responses.response_input_param import FunctionCallOutput

from koda.messages import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from koda.providers.adapter import ProviderAdapter
from koda.tools import ToolCall, ToolDefinition


class OpenAIAdapter(ProviderAdapter):
    """Adapter for converting to/from OpenAI's API format."""

    def _adapt_tool_message(self, message: ToolMessage) -> FunctionCallOutput:
        tool_output = message.tool_result.output
        output_data: dict[str, Any] = {
            "content": tool_output.content,
            "is_error": tool_output.is_error,
        }
        if tool_output.error_message:
            output_data["error_message"] = tool_output.error_message
        return FunctionCallOutput(
            call_id=message.tool_result.call_id,
            output=json.dumps(output_data),
            type="function_call_output",
        )

    def _adapt_message(self, message: Message) -> EasyInputMessageParam | FunctionCallOutput:
        if isinstance(message, UserMessage):
            return EasyInputMessageParam(role="user", content=message.content, type="message")
        if isinstance(message, AssistantMessage):
            return EasyInputMessageParam(role="assistant", content=message.content, type="message")
        if isinstance(message, SystemMessage):
            return EasyInputMessageParam(role="system", content=message.content, type="message")
        raise ValueError(f"Unknown message type: {type(message)}")

    def adapt_messages(self, messages: list[Message]) -> ResponseInputParam:
        """Convert messages to OpenAI format."""
        result: ResponseInputParam = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                result.append(self._adapt_tool_message(msg))
            else:
                result.append(self._adapt_message(msg))
        return result

    def _adapt_tool(self, tool: ToolDefinition) -> FunctionToolParam:
        """Convert a single tool definition to OpenAI format."""
        chat_tool = openai.pydantic_function_tool(
            tool.parameters_model,
            name=tool.name,
            description=tool.description,
        )

        fn = chat_tool["function"]
        return FunctionToolParam(
            type="function",
            name=fn["name"],
            description=fn.get("description"),
            parameters=fn["parameters"],
            strict=fn.get("strict", True),
        )

    def adapt_tools(self, tools: list[ToolDefinition] | None) -> list[FunctionToolParam] | Omit:
        """Convert tool definitions to OpenAI format."""
        if not tools:
            return omit
        return [self._adapt_tool(tool) for tool in tools]

    def parse_tool_calls(self, response: Response) -> list[ToolCall]:
        """Parse tool calls from OpenAI response."""
        calls: list[ToolCall] = []
        for output in response.output:
            if isinstance(output, ResponseFunctionToolCall):
                tool_name: str = output.name
                arguments: dict[str, Any] = json.loads(output.arguments)
                call_id: str = output.call_id

                calls.append(
                    ToolCall(
                        tool_name=tool_name,
                        arguments=arguments,
                        call_id=call_id,
                    ),
                )

        return calls
