"""Tests for the renderer: what messages and tool calls look like, their styles, and
the cache."""

from typing import Any

from prompt_toolkit.formatted_text import FormattedText
from rich.padding import Padding

from koda.tools import ToolCall, ToolOutput
from koda_tui import strings
from koda_tui.appearance import Tokens
from koda_tui.rendering import Renderer
from koda_tui.rendering import rich as rich_bridge
from koda_tui.rendering.diff import diff_blocks, diff_summary
from koda_tui.rendering.markdown import Markdown
from koda_tui.rendering.rich import render
from koda_tui.state import (
    AssistantMessage,
    ErrorMessage,
    Message,
    ToolMessage,
    UserMessage,
)

WIDTH = 80
TOOLS = strings.Screen.Chat.Tools


def render_message(message: Message, width: int) -> FormattedText:
    return FormattedText(Renderer().render(message, width))


class TestMessages:
    """Tests for message rendering."""

    def test_render_user_message(self) -> None:
        """render_message() should render user messages as markdown."""
        message = UserMessage("Hello")
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "Hello" in content
        assert any(Tokens.Surface.RAISED in fragment[0] for fragment in result)

    def test_render_assistant_message(self) -> None:
        """render_message() should render assistant messages as markdown."""
        message = AssistantMessage("I can help")
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "I can help" in content

    def test_render_assistant_message_with_thinking(self) -> None:
        """render_message() should keep persisted thinking content visible."""
        message = AssistantMessage("I can help", thinking="Comparing options")
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "Comparing options" in content
        assert "I can help" in content
        lines = [line.rstrip() for line in content.splitlines()]
        assert lines[:3] == ["Comparing options", "", "I can help"]

    def test_render_assistant_thinking_renders_markdown(self) -> None:
        """thinking content should be rendered through markdown, not as literal markers."""
        message = AssistantMessage("", thinking="**Exploring the meaning of 42**")
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "Exploring the meaning of 42" in content
        assert "**Exploring the meaning of 42**" not in content

    def test_render_tool_message(self) -> None:
        """render_message() should render tool messages."""
        tool_call = ToolCall(
            tool_name="search",
            arguments={"query": "test"},
            call_id="call_123",
        )
        message = ToolMessage(tool_call)
        result = render_message(message, WIDTH)
        content = "".join(t[1] for t in result)
        assert "search" in content

    def test_render_error_message(self) -> None:
        """An error shows its summary in bold above its detail."""
        result = render_message(ErrorMessage("Rate limit exceeded.", "Try again later."), WIDTH)
        lines = [line.rstrip() for line in "".join(t[1] for t in result).splitlines()]
        assert lines == ["Rate limit exceeded.", "", "Try again later."]
        assert any(
            "Rate limit" in text and Tokens.Text.STRONG in style for style, text, *_ in result
        )

    def test_render_error_without_detail_says_what_to_do(self) -> None:
        result = render_message(ErrorMessage("Not set up."), WIDTH)
        assert strings.Screen.Chat.ERROR_FALLBACK in "".join(t[1] for t in result)


class TestStyleClasses:
    """Theme-dependent styling is emitted as style classes, not baked-in colors."""

    def test_code_block_emits_pygments_classes(self) -> None:
        message = AssistantMessage("```python\nimport os\n```")
        result = render_message(message, WIDTH)
        assert ("class:pygments.keyword.namespace", "import") in result

    def test_diff_lines_emit_full_width_diff_classes(self) -> None:
        diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        result = render(diff_blocks(diff), WIDTH)
        added = "".join(fragment[1] for fragment in result if Tokens.Diff.ADD in fragment[0])
        assert any(Tokens.Diff.REMOVE in fragment[0] for fragment in result)
        assert added.rstrip("\n").endswith(" ")


def test_rich_emits_no_colors_so_every_color_comes_from_a_token() -> None:
    markdown = (
        "# H1\n## H2 *em* **strong** ~~s~~ `code`\n> [link](https://example.com)\n\n"
        "- item\n1. item\n\n| a | b |\n|---|---|\n| c | d |\n\n---\n"
        "```python\nclass A: pass\n```\n\n    indented = True\n"
    )
    diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
    renderables = [
        Padding(Markdown(markdown), 1, style=Tokens.Surface.RAISED),
        diff_blocks(diff),
    ]
    console = rich_bridge._Console(width=60)  # noqa: SLF001

    colored = [
        segment
        for renderable in renderables
        for segment in console.render(renderable)
        if segment.style
        and any(
            color and not color.is_default for color in (segment.style.color, segment.style.bgcolor)
        )
    ]

    assert colored == []


def _tool_call(
    tool_call: ToolCall,
    *,
    running: bool = False,
    content: dict[str, Any] | None = None,
) -> FormattedText:
    failed = bool(content) and content.get("exit_code", 0) != 0  # As the bash tool marks it.
    output = None if running else ToolOutput(content=content or {}, is_error=failed)
    return render_message(ToolMessage(tool_call, output), 80)


class TestToolCalls:
    """Tests for tool call rendering."""

    def test_render_tool_call(self) -> None:
        """A tool call should display the tool name."""
        tool_call = ToolCall(
            tool_name="read_file",
            arguments={"path": "/tmp/test.txt"},
            call_id="call_456",
        )
        result = _tool_call(tool_call)
        content = "".join(t[1] for t in result)
        assert "read_file" in content

    def test_render_tool_call_running(self) -> None:
        """A running tool call should display the tool name."""
        tool_call = ToolCall(
            tool_name="search",
            arguments={},
            call_id="call_789",
        )
        result = _tool_call(tool_call, running=True)
        content = "".join(t[1] for t in result)
        assert "search" in content

    def test_render_bash_tool_call_shows_command_and_result_preview(self) -> None:
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
        result = _tool_call(
            tool_call,
            content={
                "stdout": "collected 7 items\n.......\n7 passed in 0.50s\n",
                "stderr": "",
                "exit_code": 0,
                "command": "python -m pytest packages/koda/tests/tools -k bash",
                "cwd": ".",
            },
        )
        content = "".join(t[1] for t in result)
        assert "✓ bash command=python -m pytest packages/koda/tests/tools -k bash cwd=." in content
        assert "timeout_seconds=30" in content
        assert f"\n  └ {TOOLS.bash_summary(None, 3, 0)}" in content
        assert "7 passed in 0.50s" in content

    def test_render_bash_nonzero_exit_is_visually_marked_failed(self) -> None:
        """bash tool rendering should show a failure marker for non-zero exit codes."""
        tool_call = ToolCall(
            tool_name="bash",
            arguments={"command": "exit 1", "cwd": ".", "timeout_seconds": 30},
            call_id="call_bash_fail",
        )
        result = _tool_call(
            tool_call,
            content={
                "stdout": "",
                "stderr": "boom\n",
                "exit_code": 1,
                "command": "exit 1",
                "cwd": ".",
            },
        )
        content = "".join(t[1] for t in result)
        assert "✕ bash command=exit 1 cwd=. timeout_seconds=30" in content
        assert f"\n  └ {TOOLS.bash_summary(1, 0, 1)}" in content
        assert "boom" in content

    def test_render_bash_success_prefers_stdout_over_stderr(self) -> None:
        """Successful bash output should preview stdout even when stderr has content."""
        tool_call = ToolCall(
            tool_name="bash",
            arguments={"command": "example", "cwd": ".", "timeout_seconds": 30},
            call_id="call_bash_stdout",
        )
        result = _tool_call(
            tool_call,
            content={
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
        assert f"\n  └ {TOOLS.bash_summary(None, 1, 1)}" in content

    def test_render_bash_success_prefers_tail_preview(self) -> None:
        """Successful bash output should preview the tail where completion info usually lives."""
        tool_call = ToolCall(
            tool_name="bash",
            arguments={"command": "pytest", "cwd": ".", "timeout_seconds": 30},
            call_id="call_bash_tail",
        )
        stdout = "header\nline2\nline3\nline4\nline5\nline6\n7 passed in 0.50s\n"

        result = _tool_call(
            tool_call,
            content={
                "stdout": stdout,
                "stderr": "",
                "exit_code": 0,
                "command": "pytest",
                "cwd": ".",
            },
        )
        content = "".join(t[1] for t in result)

        assert TOOLS.bash_summary(None, 7, 0) in content
        assert "7 passed in 0.50s" in content
        assert "header" not in content
        assert TOOLS.truncated(7) in content

    def test_render_bash_multiline_command_is_collapsed_for_header(self) -> None:
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

        result = _tool_call(
            tool_call,
            content={
                "stdout": "274 passed in 3.10s\n",
                "stderr": "",
                "exit_code": 0,
                "command": "set -u\nprintf 'Working directory: '; pwd\nuv run pytest -q\n",
                "cwd": ".",
            },
        )
        content = "".join(t[1] for t in result)

        assert "command=set -u printf 'Working directory: '; pwd uv run pytest -q" in content
        assert "timeout_seconds=300" in content
        assert "command=set -u\n" not in content

    def test_failed_tool_without_display_shows_its_error(self) -> None:
        """A failure with no display of its own shows its error message."""
        tool_call = ToolCall(tool_name="read_file", arguments={"path": "a.py"}, call_id="c1")
        output = ToolOutput(is_error=True, error_message="File not found")

        content = "".join(t[1] for t in render_message(ToolMessage(tool_call, output), 80))

        assert "✕ read_file" in content
        assert "\n  └ File not found" in content


def test_diff_summary_counts_additions_and_deletions() -> None:
    assert diff_summary("--- a/x\n+++ b/x\n@@ -1,2 +1,1 @@\n-one\n-two\n+three\n") == (
        TOOLS.diff_summary(1, 2)
    )


def test_diff_summary_with_nothing_added() -> None:
    assert diff_summary("--- a/x\n+++ b/x\n@@ -1,1 +1,0 @@\n-gone\n") == TOOLS.diff_summary(0, 1)
