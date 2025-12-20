import json
from collections.abc import AsyncIterator
from typing import Any

from langfuse import observe
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from openai.types.responses import ResponseCompletedEvent, ResponseTextDeltaEvent

from koda.core import message
from koda.providers import Provider, TextDelta, ToolCallRequested
from koda.tools import ToolCall, ToolDefinition
from koda.utils import exceptions


class OpenAIProvider(Provider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.2",
        base_url: str | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise exceptions.ProviderValidationError("OpenAI API key cannot be empty")

        self.client: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model: str = model
        self._last_response_id: str | None = None

    @observe(name="openai.stream", as_type="generation")
    async def stream(
        self,
        messages: list[message.Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[TextDelta | ToolCallRequested]:
        if not messages:
            raise exceptions.ProviderValidationError("Messages list cannot be empty")

        input_items = self._messages_to_openai_input(messages)
        openai_tools = (
            [self._convert_tool_definition_to_openai(tool) for tool in tools] if tools else None
        )

        try:
            create_kwargs: dict[str, Any] = {
                "model": self.model,
                "input": input_items,
                "previous_response_id": self._last_response_id,
                "stream": True,
            }
            if openai_tools is not None:
                create_kwargs["tools"] = openai_tools
            stream = await self.client.responses.create(**create_kwargs)
        except RateLimitError as e:
            raise exceptions.ProviderRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except AuthenticationError as e:
            auth_error_msg = f"OpenAI authentication failed: {e}"
            raise exceptions.ProviderAuthenticationError(auth_error_msg) from e
        except (APIConnectionError, APITimeoutError) as e:
            raise exceptions.ProviderAPIError(f"OpenAI connection error: {e}") from e
        except APIError as e:
            raise exceptions.ProviderAPIError(f"OpenAI API error: {e}") from e

        async for event in stream:
            if isinstance(event, ResponseTextDeltaEvent):
                yield TextDelta(text=event.delta)
            elif isinstance(event, ResponseCompletedEvent):
                self._last_response_id = event.response.id
                tool_calls = self._parse_tool_calls_from_response(event.response)
                for call in tool_calls:
                    yield ToolCallRequested(call=call)

    def reset_state(self) -> None:
        self._last_response_id = None

    def _messages_to_openai_input(self, messages: list[message.Message]) -> list[dict[str, Any]]:
        """Convert messages to OpenAI Responses API structured input items.

        Converts system/user/assistant messages to role/content dicts.
        Converts ToolResultMessage to function_call_output items with call_id.
        Ignores ToolCallMessage (OpenAI already knows about them via previous_response_id).
        """
        input_items: list[dict[str, Any]] = []

        for msg in messages:
            # Ignore ToolCallMessage - OpenAI already knows about tool calls
            # via previous_response_id
            if isinstance(msg, message.ToolCallMessage):
                continue

            # Convert ToolResultMessage to function_call_output
            if isinstance(msg, message.ToolResultMessage):
                # Use call_id from message or fall back to result.call_id
                call_id = msg.call_id or (msg.result.call_id if msg.result.call_id else None)
                if call_id is None:
                    # Skip if no call_id - can't match to tool call
                    continue

                # Build output JSON with content, is_error, and error_message
                output_data: dict[str, Any] = {
                    "content": msg.result.content,
                    "is_error": msg.result.is_error,
                }
                if msg.result.error_message:
                    output_data["error_message"] = msg.result.error_message

                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(output_data),
                    }
                )
                continue

            # Convert regular messages (system/user/assistant) to role/content dicts
            if isinstance(
                msg, (message.SystemMessage, message.UserMessage, message.AssistantMessage)
            ):
                input_items.append(
                    {
                        "role": msg.role.value,
                        "content": msg.content,
                    }
                )

        return input_items

    def _convert_tool_definition_to_openai(self, tool: ToolDefinition) -> dict[str, Any]:
        return {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }

    def _parse_tool_calls_from_response(self, response: Any) -> list[ToolCall]:
        calls: list[ToolCall] = []

        output = getattr(response, "output", None) or []
        for item in output:
            # item can be pydantic model; access via attributes or dict-ish
            item_type = getattr(item, "type", None) or (
                item.get("type") if isinstance(item, dict) else None
            )

            # Depending on SDK, function/tool calls may show up like this
            if item_type in ("function_call", "tool_call"):
                tool_name = getattr(item, "name", None) or (
                    item.get("name") if isinstance(item, dict) else None
                )
                raw_args = getattr(item, "arguments", None) or (
                    item.get("arguments") if isinstance(item, dict) else None
                )
                call_id = (
                    getattr(item, "call_id", None)
                    or getattr(item, "id", None)
                    or (item.get("call_id") if isinstance(item, dict) else None)
                    or (item.get("id") if isinstance(item, dict) else None)
                )

                if tool_name is None:
                    continue

                arguments: dict[str, Any]
                if raw_args is None:
                    arguments = {}
                elif isinstance(raw_args, dict):
                    arguments = raw_args
                elif isinstance(raw_args, str):
                    # arguments is often a JSON string
                    try:
                        arguments = json.loads(raw_args) if raw_args.strip() else {}
                    except Exception:
                        # fallback: keep empty, or store raw in a special key
                        arguments = {"_raw": raw_args}
                else:
                    arguments = {"_raw": raw_args}

                calls.append(
                    ToolCall(
                        tool_name=tool_name,
                        arguments=arguments,
                        call_id=str(call_id) if call_id is not None else None,
                    )
                )

        return calls
