"""Tests for rendering tool calls and their results."""

from typing import Any

from prompt_toolkit.formatted_text import FormattedText

from koda.tools import ToolCall, ToolOutput
from koda_tui.rendering.diff import diff_summary
from koda_tui.rendering.rich import render
from koda_tui.rendering.tools import render_tool_call


def _tool_call(
    tool_call: ToolCall,
    *,
    running: bool = False,
    content: dict[str, Any] | None = None,
) -> FormattedText:
    output = None if running else ToolOutput(content=content or {})
    return render(render_tool_call(tool_call, output), 80)


class TestToolCalls:
    """Tests for tool call rendering."""

    def test_render_tool_call(self) -> None:
        """render_tool_call() should display the tool name."""
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
        assert "timeout=30s" in content
        assert "\n  └ succeeded, stdout 3 lines, stderr empty" in content
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
        assert "✕ bash command=exit 1 cwd=. timeout=30s" in content
        assert "\n  └ exit 1, stdout 0 lines, stderr 1 lines" in content
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
        assert "\n  └ succeeded, stdout 1 lines, stderr 1 lines" in content

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

        assert "succeeded, stdout 7 lines, stderr empty" in content
        assert "7 passed in 0.50s" in content
        assert "header" not in content
        assert "[truncated, 7 total lines]" in content

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
        assert "timeout=300s" in content
        assert "command=set -u\n" not in content

    def test_failed_tool_without_display_shows_its_error(self) -> None:
        """A failure with no display of its own shows its error message."""
        tool_call = ToolCall(tool_name="read_file", arguments={"path": "a.py"}, call_id="c1")
        output = ToolOutput(is_error=True, error_message="File not found")

        content = "".join(t[1] for t in render(render_tool_call(tool_call, output), 80))

        assert "✕ read_file" in content
        assert "\n  └ File not found" in content


def test_diff_summary_counts_additions_and_deletions() -> None:
    assert diff_summary("--- a/x\n+++ b/x\n@@ -1,2 +1,1 @@\n-one\n-two\n+three\n") == (
        "1 addition, 2 deletions"
    )


def test_diff_summary_with_nothing_added() -> None:
    assert diff_summary("--- a/x\n+++ b/x\n@@ -1,1 +1,0 @@\n-gone\n") == "0 additions, 1 deletion"
