from rich.text import Text

from koda.tools import ToolCall
from koda_tui.rendering import MessageRenderer
from koda_tui.state import Message, MessageRole


class TestMessageRendererConvert:
    """Tests for basic conversion methods."""

    def test_convert_text(self, converter: MessageRenderer) -> None:
        """convert() should convert Rich Text to FormattedText."""
        text = Text("Hello world")
        result = converter.convert(text)
        # FormattedText is a list of (style, text) tuples
        content = "".join(t[1] for t in result)
        assert "Hello world" in content

    def test_convert_styled_text(self, converter: MessageRenderer) -> None:
        """convert() should preserve styling information."""
        text = Text()
        text.append("Bold", style="bold")
        result = converter.convert(text)
        content = "".join(t[1] for t in result)
        assert "Bold" in content


class TestMessageRendererMessages:
    """Tests for message rendering."""

    def test_render_user_message(self, converter: MessageRenderer) -> None:
        """render_message() should render user messages as markdown."""
        message = Message(role=MessageRole.USER, content="Hello")
        result = converter.render_message(message)
        content = "".join(t[1] for t in result)
        assert "Hello" in content

    def test_render_assistant_message(self, converter: MessageRenderer) -> None:
        """render_message() should render assistant messages as markdown."""
        message = Message(role=MessageRole.ASSISTANT, content="I can help")
        result = converter.render_message(message)
        content = "".join(t[1] for t in result)
        assert "I can help" in content

    def test_render_tool_message(self, converter: MessageRenderer) -> None:
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


class TestMessageRendererToolCalls:
    """Tests for tool call rendering."""

    def test_render_tool_call(self, converter: MessageRenderer) -> None:
        """render_tool_call() should display the tool name."""
        tool_call = ToolCall(
            tool_name="read_file",
            arguments={"path": "/tmp/test.txt"},
            call_id="call_456",
        )
        result = converter.render_tool_call(tool_call)
        content = "".join(t[1] for t in result)
        assert "read_file" in content

    def test_render_tool_call_running(self, converter: MessageRenderer) -> None:
        """render_tool_call() with running=True should display the tool name."""
        tool_call = ToolCall(
            tool_name="search",
            arguments={},
            call_id="call_789",
        )
        result = converter.render_tool_call(tool_call, running=True)
        content = "".join(t[1] for t in result)
        assert "search" in content


class TestMessageRendererStreaming:
    """Tests for streaming content rendering."""

    def test_render_streaming_content(self, converter: MessageRenderer) -> None:
        """render_streaming_content() should show content with cursor."""
        result = converter.render_streaming_content("Hello wor")
        content = "".join(t[1] for t in result)
        assert "Hello wor" in content
        # Should have cursor block
        assert "\u2588" in content
