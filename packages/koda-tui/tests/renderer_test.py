"""Tests for the renderer module."""

from rich.console import Console

from koda.tools import ToolCall
from koda_tui.renderer import RichRenderer

from .conftest import get_output


class TestRichRendererPrint:
    """Tests for basic print methods."""

    def test_print_outputs_message(self, renderer: RichRenderer, captured_console: Console) -> None:
        """print() should output the message."""
        renderer.print("Hello world")
        output = get_output(captured_console)
        assert "Hello world" in output

    def test_print_assistant_includes_prefix(
        self, renderer: RichRenderer, captured_console: Console
    ) -> None:
        """print_assistant() should include 'Koda:' prefix."""
        renderer.print_assistant("I can help with that")
        output = get_output(captured_console)
        assert "Koda:" in output
        assert "I can help with that" in output

    def test_print_error_includes_error_prefix(
        self, renderer: RichRenderer, captured_console: Console
    ) -> None:
        """print_error() should include 'Error:' in output."""
        renderer.print_error("Something went wrong")
        output = get_output(captured_console)
        assert "Error:" in output
        assert "Something went wrong" in output

    def test_print_info_outputs_message(
        self, renderer: RichRenderer, captured_console: Console
    ) -> None:
        """print_info() should output the message."""
        renderer.print_info("Some info")
        output = get_output(captured_console)
        assert "Some info" in output


class TestRichRendererToolCall:
    """Tests for tool call rendering."""

    def test_print_tool_call_shows_tool_name(
        self, renderer: RichRenderer, captured_console: Console
    ) -> None:
        """print_tool_call() should display the tool name."""
        tool_call = ToolCall(
            tool_name="search",
            arguments={"query": "test"},
            call_id="call_123",
        )
        renderer.print_tool_call(tool_call)
        output = get_output(captured_console)
        assert "search" in output

    def test_print_tool_call_includes_label(
        self, renderer: RichRenderer, captured_console: Console
    ) -> None:
        """print_tool_call() should include 'Tool call:' label."""
        tool_call = ToolCall(
            tool_name="read_file",
            arguments={"path": "/tmp/test.txt"},  # noqa: S108
            call_id="call_456",
        )
        renderer.print_tool_call(tool_call)
        output = get_output(captured_console)
        assert "Tool call:" in output


class TestRichRendererStreaming:
    """Tests for streaming output methods."""

    def test_write_outputs_text(self, renderer: RichRenderer, captured_console: Console) -> None:
        """write() should output text."""
        renderer.write("streaming ")
        renderer.write("content")
        output = get_output(captured_console)
        assert "streaming" in output
        assert "content" in output

    def test_flush_adds_newline(self, renderer: RichRenderer, captured_console: Console) -> None:
        """flush() should add a newline."""
        renderer.write("some text")
        renderer.flush()
        output = get_output(captured_console)
        assert output.endswith("\n")
