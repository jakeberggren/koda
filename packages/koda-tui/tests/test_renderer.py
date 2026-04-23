from rich.text import Text

from koda_service.types import ToolCall
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

    def test_render_assistant_message_with_thinking(self, converter: MessageRenderer) -> None:
        """render_message() should keep persisted thinking content visible."""
        message = Message(
            role=MessageRole.ASSISTANT,
            content="I can help",
            thinking_content="Comparing options",
        )
        result = converter.render_message(message)
        content = "".join(t[1] for t in result)
        assert "Comparing options" in content
        assert "I can help" in content

    def test_render_assistant_thinking_renders_markdown(self, converter: MessageRenderer) -> None:
        """thinking content should be rendered through markdown, not as literal markers."""
        message = Message(
            role=MessageRole.ASSISTANT,
            content="",
            thinking_content="**Exploring the meaning of 42**",
        )
        result = converter.render_message(message)
        content = "".join(t[1] for t in result)
        assert "Exploring the meaning of 42" in content
        assert "**Exploring the meaning of 42**" not in content

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

    def test_render_bash_tool_call_shows_command_and_result_preview(
        self, converter: MessageRenderer
    ) -> None:
        """bash tool rendering should show command details and a result preview."""
        tool_call = ToolCall(
            tool_name="bash",
            arguments={
                "command": "python -m pytest packages/koda/tests/tools -k bash",
                "cwd": ".",
                "timeout_seconds": 30,
            },
            call_id="call_bash",
        )
        result = converter.render_tool_call(
            tool_call,
            result_content={
                "stdout": "collected 7 items\n.......\n7 passed in 0.50s\n",
                "stderr": "",
                "exit_code": 0,
                "command": "python -m pytest packages/koda/tests/tools -k bash",
                "cwd": ".",
            },
        )
        content = "".join(t[1] for t in result)
        assert "✓ bash command=python -m pytest packages/koda/tests/tools -k bash cwd=." in content
        assert "timeout=30s" in content
        assert "\n  └ succeeded, stdout 3 lines, stderr empty" in content
        assert "7 passed in 0.50s" in content

    def test_render_bash_nonzero_exit_is_visually_marked_failed(
        self, converter: MessageRenderer
    ) -> None:
        """bash tool rendering should show a failure marker for non-zero exit codes."""
        tool_call = ToolCall(
            tool_name="bash",
            arguments={"command": "exit 1", "cwd": ".", "timeout_seconds": 30},
            call_id="call_bash_fail",
        )
        result = converter.render_tool_call(
            tool_call,
            result_content={
                "stdout": "",
                "stderr": "boom\n",
                "exit_code": 1,
                "command": "exit 1",
                "cwd": ".",
            },
        )
        content = "".join(t[1] for t in result)
        assert "✕ bash command=exit 1 cwd=. timeout=30s" in content
        assert "\n  └ exit 1, stdout 0 lines, stderr 1 lines" in content
        assert "boom" in content

    def test_render_bash_success_prefers_stdout_over_stderr(
        self,
        converter: MessageRenderer,
    ) -> None:
        """Successful bash output should preview stdout even when stderr has content."""
        tool_call = ToolCall(
            tool_name="bash",
            arguments={"command": "example", "cwd": ".", "timeout_seconds": 30},
            call_id="call_bash_stdout",
        )
        result = converter.render_tool_call(
            tool_call,
            result_content={
                "stdout": "all good\n",
                "stderr": "warning\n",
                "exit_code": 0,
                "command": "example",
                "cwd": ".",
            },
        )
        content = "".join(t[1] for t in result)
        assert "all good" in content
        assert "warning" not in content
        assert "\n  └ succeeded, stdout 1 lines, stderr 1 lines" in content

    def test_render_bash_success_prefers_tail_preview(self, converter: MessageRenderer) -> None:
        """Successful bash output should preview the tail where completion info usually lives."""
        tool_call = ToolCall(
            tool_name="bash",
            arguments={"command": "pytest", "cwd": ".", "timeout_seconds": 30},
            call_id="call_bash_tail",
        )
        stdout = "header\nline2\nline3\nline4\nline5\nline6\n7 passed in 0.50s\n"

        result = converter.render_tool_call(
            tool_call,
            result_content={
                "stdout": stdout,
                "stderr": "",
                "exit_code": 0,
                "command": "pytest",
                "cwd": ".",
            },
        )
        content = "".join(t[1] for t in result)

        assert "succeeded, stdout 7 lines, stderr empty" in content
        assert "7 passed in 0.50s" in content
        assert "header" not in content
        assert "[truncated, 7 total lines]" in content

    def test_render_bash_multiline_command_is_collapsed_for_header(
        self, converter: MessageRenderer
    ) -> None:
        """Multiline bash commands should render as a compact single-line preview."""
        tool_call = ToolCall(
            tool_name="bash",
            arguments={
                "command": "set -u\nprintf 'Working directory: '; pwd\nuv run pytest -q\n",
                "cwd": ".",
                "timeout_seconds": 300,
            },
            call_id="call_bash_multiline",
        )

        result = converter.render_tool_call(
            tool_call,
            result_content={
                "stdout": "274 passed in 3.10s\n",
                "stderr": "",
                "exit_code": 0,
                "command": "set -u\nprintf 'Working directory: '; pwd\nuv run pytest -q\n",
                "cwd": ".",
            },
        )
        content = "".join(t[1] for t in result)

        assert "command=set -u printf 'Working directory: '; pwd uv run pytest -q" in content
        assert "timeout=300s" in content
        assert "command=set -u\n" not in content


class TestMessageRendererStreaming:
    """Tests for streaming content rendering."""

    def test_render_streaming_content(self, converter: MessageRenderer) -> None:
        """render_streaming_content() should show content with cursor."""
        result = converter.render_streaming_content("Hello wor")
        content = "".join(t[1] for t in result)
        assert "Hello wor" in content
        # Should have cursor block
        assert "\u2588" in content

    def test_render_thinking_content_renders_markdown(self, converter: MessageRenderer) -> None:
        """render_thinking_content() should parse markdown markers."""
        result = converter.render_thinking_content("**Exploring the meaning of 42**")
        content = "".join(t[1] for t in result)
        assert "Exploring the meaning of 42" in content
        assert "**Exploring the meaning of 42**" not in content
