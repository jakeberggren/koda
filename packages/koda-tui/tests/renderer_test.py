"""Tests for the rendering converter module."""

from rich.text import Text

from koda.tools import ToolCall
from koda_tui.app import AppState, Message, MessageRole
from koda_tui.rendering import RichToPromptToolkit


class TestRichToPromptToolkitConvert:
    """Tests for basic conversion methods."""

    def test_convert_text(self, converter: RichToPromptToolkit) -> None:
        """convert() should convert Rich Text to FormattedText."""
        text = Text("Hello world")
        result = converter.convert(text)
        # FormattedText is a list of (style, text) tuples
        content = "".join(t[1] for t in result)
        assert "Hello world" in content

    def test_convert_styled_text(self, converter: RichToPromptToolkit) -> None:
        """convert() should preserve styling information."""
        text = Text()
        text.append("Bold", style="bold")
        result = converter.convert(text)
        content = "".join(t[1] for t in result)
        assert "Bold" in content


class TestRichToPromptToolkitMessages:
    """Tests for message rendering."""

    def test_render_user_message(self, converter: RichToPromptToolkit) -> None:
        """render_message() should render user messages as markdown."""
        message = Message(role=MessageRole.USER, content="Hello")
        result = converter.render_message(message)
        content = "".join(t[1] for t in result)
        assert "Hello" in content

    def test_render_assistant_message(self, converter: RichToPromptToolkit) -> None:
        """render_message() should render assistant messages in a KODA panel."""
        message = Message(role=MessageRole.ASSISTANT, content="I can help")
        result = converter.render_message(message)
        content = "".join(t[1] for t in result)
        assert "KODA" in content
        assert "I can help" in content

    def test_render_tool_message(self, converter: RichToPromptToolkit) -> None:
        """render_message() should render tool messages."""
        tool_call = ToolCall(
            tool_name="search",
            arguments={"query": "test"},
            call_id="call_123",
        )
        message = Message(
            role=MessageRole.TOOL,
            content="Tool: search",
            tool_call=tool_call,
        )
        result = converter.render_message(message)
        content = "".join(t[1] for t in result)
        assert "search" in content


class TestRichToPromptToolkitToolCalls:
    """Tests for tool call rendering."""

    def test_render_tool_call(self, converter: RichToPromptToolkit) -> None:
        """render_tool_call() should display the tool name."""
        tool_call = ToolCall(
            tool_name="read_file",
            arguments={"path": "/tmp/test.txt"},  # noqa: S108
            call_id="call_456",
        )
        result = converter.render_tool_call(tool_call)
        content = "".join(t[1] for t in result)
        assert "read_file" in content

    def test_render_tool_spinner(self, converter: RichToPromptToolkit) -> None:
        """render_tool_spinner() should show running indicator."""
        result = converter.render_tool_spinner("search")
        content = "".join(t[1] for t in result)
        assert "search" in content
        assert "Running" in content


class TestRichToPromptToolkitStreaming:
    """Tests for streaming content rendering."""

    def test_render_streaming_content(self, converter: RichToPromptToolkit) -> None:
        """render_streaming_content() should show content with cursor in KODA panel."""
        result = converter.render_streaming_content("Hello wor")
        content = "".join(t[1] for t in result)
        assert "KODA" in content
        assert "Hello wor" in content
        # Should have cursor block
        assert "\u2588" in content


class TestAppState:
    """Tests for application state management."""

    def test_add_user_message(self, state: AppState) -> None:
        """add_user_message() should add message to history."""
        state.add_user_message("Hello")
        assert len(state.messages) == 1
        assert state.messages[0].role == MessageRole.USER
        assert state.messages[0].content == "Hello"

    def test_streaming_lifecycle(self, state: AppState) -> None:
        """Streaming should go through start, append, finish cycle."""
        state.start_streaming()
        assert state.is_streaming is True
        assert state.current_streaming_content == ""

        state.append_delta("Hello ")
        state.append_delta("world")
        assert state.current_streaming_content == "Hello world"

        state.finish_streaming()
        assert state.is_streaming is False
        assert state.current_streaming_content == ""
        assert len(state.messages) == 1
        assert state.messages[0].content == "Hello world"

    def test_exit_request(self, state: AppState) -> None:
        """request_exit() should require two calls to exit."""
        assert state.request_exit() is False
        assert state.request_exit() is True

    def test_reset_exit_request(self, state: AppState) -> None:
        """reset_exit_request() should reset the exit flag."""
        state.request_exit()
        state.reset_exit_request()
        assert state.request_exit() is False
