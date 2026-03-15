import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from koda_service.types import (
    TextDelta,
    ToolCall,
    ToolCallRequested,
    ToolCallResult,
    ToolOutput,
    ToolResult,
)
from koda_tui.app.streaming import StreamProcessor
from koda_tui.state import AppState, MessageRole


@pytest.fixture
def processor(state: AppState) -> StreamProcessor:
    """A StreamProcessor for testing."""
    return StreamProcessor(state=state, invalidate=lambda: None)


class TestStreamProcessor:
    """Tests for StreamProcessor async streaming."""

    @pytest.mark.asyncio
    async def test_stream_text_only(self, state: AppState, processor: StreamProcessor) -> None:
        """Streaming text should append to messages."""
        client = AsyncMock()

        async def mock_chat(_msg: str) -> AsyncIterator:
            yield TextDelta(text="Hello ")
            yield TextDelta(text="world")

        client.chat = mock_chat

        await processor.stream("hi", client)

        assert state.is_streaming is False
        user_msg, assistant_msg = state.messages
        assert user_msg.role == MessageRole.USER
        assert user_msg.content == "hi"
        assert assistant_msg.role == MessageRole.ASSISTANT
        assert assistant_msg.content == "Hello world"

    @pytest.mark.asyncio
    async def test_stream_with_tool_call(self, state: AppState, processor: StreamProcessor) -> None:
        """Streaming with tool calls should track tools."""
        client = AsyncMock()
        tool = ToolCall(tool_name="read_file", arguments={"path": "/tmp"}, call_id="c1")

        async def mock_chat(_msg: str) -> AsyncIterator:
            yield TextDelta(text="Let me check...")
            yield ToolCallRequested(call=tool)
            yield ToolCallResult(
                tool_name="read_file",
                result=ToolResult(
                    call_id="c1",
                    output=ToolOutput(content={"data": "file contents"}, display="file contents"),
                ),
            )
            yield TextDelta(text="Done!")

        client.chat = mock_chat

        await processor.stream("read file", client)

        assert state.is_streaming is False
        user_msg, first_assistant, tool_msg, second_assistant = state.messages
        assert user_msg.role == MessageRole.USER
        assert first_assistant.role == MessageRole.ASSISTANT
        assert first_assistant.content == "Let me check..."
        assert tool_msg.role == MessageRole.TOOL
        assert tool_msg.tool_running is False
        assert tool_msg.tool_result_display == "file contents"
        assert second_assistant.role == MessageRole.ASSISTANT
        assert second_assistant.content == "Done!"

    @pytest.mark.asyncio
    async def test_stream_tool_error(self, state: AppState, processor: StreamProcessor) -> None:
        """Tool errors should be flagged on the message."""
        client = AsyncMock()
        tool = ToolCall(tool_name="read_file", arguments={"path": "/bad"}, call_id="c1")

        async def mock_chat(_msg: str) -> AsyncIterator:
            yield ToolCallRequested(call=tool)
            yield ToolCallResult(
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

        assert state.messages[1].role == MessageRole.TOOL
        assert state.messages[1].tool_error is True
        assert state.messages[1].tool_error_message == "File not found"
        assert state.messages[1].tool_result_display == "File not found"

    @pytest.mark.asyncio
    async def test_stream_handles_exception(
        self, state: AppState, processor: StreamProcessor
    ) -> None:
        """Unknown exceptions should show a generic user-safe error message."""
        client = AsyncMock()

        async def mock_chat(_msg: str) -> AsyncIterator:
            yield TextDelta(text="Starting...")
            raise ValueError("Something went wrong")
            yield  # Make it a generator

        client.chat = mock_chat

        await processor.stream("do something", client)

        assert state.is_streaming is False
        _user_msg, assistant_msg = state.messages
        assert "Starting..." in assistant_msg.content
        assert (
            "An unexpected error occurred while processing the response." in assistant_msg.content
        )

    @pytest.mark.asyncio
    async def test_cancel_stream(self, state: AppState, processor: StreamProcessor) -> None:
        """Cancelling stream should stop processing."""
        client = AsyncMock()

        async def mock_chat(_msg: str) -> AsyncIterator:
            yield TextDelta(text="Start")
            # Simulate long-running stream that gets cancelled

            await asyncio.sleep(10)
            yield TextDelta(text="Never reached")

        client.chat = mock_chat

        # Start streaming in background
        task = asyncio.create_task(processor.stream("test", client))
        await asyncio.sleep(0.05)  # Let it start

        processor.cancel_stream()
        await task  # Should complete quickly due to cancellation

        assert state.is_streaming is False
