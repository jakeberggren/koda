import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from koda.agent import AgentTextDelta, AgentToolCallRequested, AgentToolCompleted
from koda.tools import ToolCall, ToolOutput, ToolResult
from koda_service import ChatRequest
from koda_service.exceptions import ServiceConnectionError, ServiceRateLimitError
from koda_tui.app.conversation import Conversation
from koda_tui.app.streaming import StreamProcessor
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


@pytest.fixture
def processor(state: AppState) -> StreamProcessor:
    """A StreamProcessor for testing."""
    return StreamProcessor(conversation=Conversation(state), invalidate=lambda: None)


class TestStreamProcessor:
    """Tests for StreamProcessor async streaming."""

    @pytest.mark.asyncio
    async def test_stream_text_only(self, state: AppState, processor: StreamProcessor) -> None:
        """Streaming text should append to messages."""
        client = AsyncMock()

        async def mock_chat(_request: ChatRequest) -> AsyncIterator:
            yield AgentTextDelta(text="Hello ")
            yield AgentTextDelta(text="world")

        client.chat = mock_chat

        await processor.stream("hi", client)

        assert state.responding is False
        user_msg, assistant_msg = state.messages
        assert isinstance(user_msg, UserMessage)
        assert _text(user_msg) == "hi"
        assert isinstance(assistant_msg, AssistantMessage)
        assert _text(assistant_msg) == "Hello world"

    @pytest.mark.asyncio
    async def test_stream_with_tool_call(self, state: AppState, processor: StreamProcessor) -> None:
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

        await processor.stream("read file", client)

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
    async def test_stream_tool_error(self, state: AppState, processor: StreamProcessor) -> None:
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

        await processor.stream("read bad file", client)

        assert isinstance(state.messages[1], ToolMessage)
        assert _output(state.messages[1]).is_error is True
        assert _output(state.messages[1]).error_message == "File not found"
        assert _output(state.messages[1]).display is None

    @pytest.mark.asyncio
    async def test_stream_handles_rate_limit_error(
        self, state: AppState, processor: StreamProcessor
    ) -> None:
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

        await processor.stream("do something", client)

        assert state.responding is False
        _user_msg, assistant_msg = state.messages
        assert "Starting..." in _text(assistant_msg)
        assert "**Rate limit exceeded.**" in _text(assistant_msg)
        assert "quota hit" in _text(assistant_msg)

    @pytest.mark.asyncio
    async def test_stream_propagates_unexpected_exception(self, processor: StreamProcessor) -> None:
        """Unexpected exceptions should escape local handling."""
        client = AsyncMock()

        async def mock_chat(_request: ChatRequest) -> AsyncIterator:
            raise ValueError("Something went wrong")
            yield  # Make it a generator

        client.chat = mock_chat

        with pytest.raises(ValueError, match="Something went wrong"):
            await processor.stream("do something", client)

    @pytest.mark.asyncio
    async def test_stream_handles_connection_error(
        self, state: AppState, processor: StreamProcessor
    ) -> None:
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

        await processor.stream("do something", client)

        assert state.responding is False
        _user_msg, assistant_msg = state.messages
        assert "**Connection error.**" in _text(assistant_msg)
        assert "network down" in _text(assistant_msg)

    @pytest.mark.asyncio
    async def test_cancel_stream(self, state: AppState, processor: StreamProcessor) -> None:
        """Cancelling stream should stop processing."""
        client = AsyncMock()

        async def mock_chat(_request: ChatRequest) -> AsyncIterator:
            yield AgentTextDelta(text="Start")
            # Simulate long-running stream that gets cancelled

            await asyncio.sleep(10)
            yield AgentTextDelta(text="Never reached")

        client.chat = mock_chat

        # Start streaming in background
        task = asyncio.create_task(processor.stream("test", client))
        await asyncio.sleep(0.05)  # Let it start

        processor.cancel_stream()
        await task  # Should complete quickly due to cancellation

        assert state.responding is False
