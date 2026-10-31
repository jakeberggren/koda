import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from koda.agent import AgentTextDelta, AgentToolCallRequested, AgentToolCompleted
from koda.tools import ToolCall, ToolOutput, ToolResult
from koda_service import ChatRequest
from koda_service.exceptions import ServiceConnectionError, ServiceRateLimitError
from koda_tui.messaging import Conversation, Outbox
from koda_tui.state import (
    AppState,
    AssistantMessage,
    Message,
    ToolMessage,
    UserMessage,
)


def _tool(message: Message) -> ToolMessage:
    assert isinstance(message, ToolMessage)
    return message


def _output(message: Message) -> ToolOutput:
    output = _tool(message).result
    assert output is not None
    return output


def _reply(message: Message) -> AssistantMessage:
    assert isinstance(message, AssistantMessage)
    return message


def _text(message: Message) -> str:
    assert isinstance(message, UserMessage | AssistantMessage)
    return message.text


def _outbox(state: AppState, service: object) -> Outbox:
    conversation = Conversation(state)
    return Outbox(state=state, conversation=conversation, service=service, invalidate=lambda: None)  # type: ignore


async def _send(state: AppState, service: object, text: str) -> None:
    """Submit ``text`` while idle, and wait for its response to end."""
    outbox = _outbox(state, service)
    outbox.submit(text, steer=False)
    assert outbox._sending is not None  # noqa: SLF001
    await outbox._sending  # noqa: SLF001


class TestSending:
    """A message's response, applied to the conversation."""

    @pytest.mark.asyncio
    async def test_stream_text_only(self, state: AppState) -> None:
        """Streaming text should append to messages."""
        client = AsyncMock()

        async def mock_chat(_request: ChatRequest) -> AsyncIterator:
            yield AgentTextDelta(text="Hello ")
            yield AgentTextDelta(text="world")

        client.chat = mock_chat

        await _send(state, client, "hi")

        assert state.responding is False
        user_msg, assistant_msg = state.messages
        assert isinstance(user_msg, UserMessage)
        assert _text(user_msg) == "hi"
        assert isinstance(assistant_msg, AssistantMessage)
        assert _text(assistant_msg) == "Hello world"

    @pytest.mark.asyncio
    async def test_stream_with_tool_call(self, state: AppState) -> None:
        """Streaming with tool calls should track tools."""
        client = AsyncMock()
        tool = ToolCall(tool_name="read_file", arguments={"path": "/tmp"}, call_id="c1")

        async def mock_chat(_request: ChatRequest) -> AsyncIterator:
            yield AgentTextDelta(text="Let me check...")
            yield AgentToolCallRequested(call=tool)
            yield AgentToolCompleted(
                tool_name="read_file",
                result=ToolResult(
                    call_id="c1",
                    output=ToolOutput(content={"data": "file contents"}, display="file contents"),
                ),
            )
            yield AgentTextDelta(text="Done!")

        client.chat = mock_chat

        await _send(state, client, "read file")

        assert state.responding is False
        user_msg, first_assistant, tool_msg, second_assistant = state.messages
        assert isinstance(user_msg, UserMessage)
        assert isinstance(first_assistant, AssistantMessage)
        assert _text(first_assistant) == "Let me check..."
        assert isinstance(tool_msg, ToolMessage)
        assert _tool(tool_msg).result is not None
        assert _output(tool_msg).display == "file contents"
        assert _output(tool_msg).content == {"data": "file contents"}
        assert isinstance(second_assistant, AssistantMessage)
        assert _text(second_assistant) == "Done!"

    @pytest.mark.asyncio
    async def test_stream_tool_error(self, state: AppState) -> None:
        """Tool errors should be flagged on the message."""
        client = AsyncMock()
        tool = ToolCall(tool_name="read_file", arguments={"path": "/bad"}, call_id="c1")

        async def mock_chat(_request: ChatRequest) -> AsyncIterator:
            yield AgentToolCallRequested(call=tool)
            yield AgentToolCompleted(
                tool_name="read_file",
                result=ToolResult(
                    call_id="c1",
                    output=ToolOutput(
                        content={},
                        is_error=True,
                        error_message="File not found",
                    ),
                ),
            )

        client.chat = mock_chat

        await _send(state, client, "read bad file")

        assert isinstance(state.messages[1], ToolMessage)
        assert _output(state.messages[1]).is_error is True
        assert _output(state.messages[1]).error_message == "File not found"
        assert _output(state.messages[1]).display is None

    @pytest.mark.asyncio
    async def test_stream_handles_rate_limit_error(self, state: AppState) -> None:
        """Rate limit failures should show a user-friendly inline message."""
        client = AsyncMock()

        async def mock_chat(_request: ChatRequest) -> AsyncIterator:
            yield AgentTextDelta(text="Starting...")
            raise ServiceRateLimitError(
                summary="Rate limit exceeded.",
                detail=(
                    "openai rate limit exceeded: quota hit\n\n"
                    "Please check your plan and billing details."
                ),
                message="openai rate limit exceeded: quota hit",
            )
            yield  # Make it a generator

        client.chat = mock_chat

        await _send(state, client, "do something")

        assert state.responding is False
        _user_msg, assistant_msg = state.messages
        assert "Starting..." in _text(assistant_msg)
        assert "**Rate limit exceeded.**" in _text(assistant_msg)
        assert "quota hit" in _text(assistant_msg)

    @pytest.mark.asyncio
    async def test_stream_propagates_unexpected_exception(self, state: AppState) -> None:
        """Unexpected exceptions should escape local handling."""
        client = AsyncMock()

        async def mock_chat(_request: ChatRequest) -> AsyncIterator:
            raise ValueError("Something went wrong")
            yield  # Make it a generator

        client.chat = mock_chat

        with pytest.raises(ValueError, match="Something went wrong"):
            await _send(state, client, "do something")

    @pytest.mark.asyncio
    async def test_stream_handles_connection_error(self, state: AppState) -> None:
        """Connection failures should show recovery guidance."""
        client = AsyncMock()

        async def mock_chat(_request: ChatRequest) -> AsyncIterator:
            raise ServiceConnectionError(
                summary="Connection error.",
                detail=(
                    "openai connection error: network down\n\n"
                    "Please check your internet connection and try again."
                ),
                message="openai connection error: network down",
            )
            yield  # Make it a generator

        client.chat = mock_chat

        await _send(state, client, "do something")

        assert state.responding is False
        _user_msg, assistant_msg = state.messages
        assert "**Connection error.**" in _text(assistant_msg)
        assert "network down" in _text(assistant_msg)

    @pytest.mark.asyncio
    async def test_cancel_stream(self, state: AppState) -> None:
        """Cancelling stream should stop processing."""
        client = AsyncMock()

        async def mock_chat(_request: ChatRequest) -> AsyncIterator:
            yield AgentTextDelta(text="Start")
            # Simulate long-running stream that gets cancelled

            await asyncio.sleep(10)
            yield AgentTextDelta(text="Never reached")

        client.chat = mock_chat

        outbox = _outbox(state, client)
        outbox.submit("test", steer=False)
        await asyncio.sleep(0.05)  # Let it start

        outbox.cancel()
        assert outbox._sending is not None  # noqa: SLF001
        await outbox._sending  # noqa: SLF001  # Ends quickly, being cancelled.

        assert state.responding is False
