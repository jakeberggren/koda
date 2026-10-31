"""Tool calls: a status line with the tool's arguments, and its result below."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rich.console import Group
from rich.text import Text

from koda_tui.appearance import Tokens
from koda_tui.rendering.diff import diff_blocks, diff_summary, is_diff

if TYPE_CHECKING:
    from collections.abc import Callable

    from rich.console import RenderableType

    from koda.tools import ToolCall, ToolOutput

type Arguments = dict[str, object]
type Content = dict[str, Any] | None

RESULT = "  └ "  # Leads each line of a result.
ELLIPSIS = "…"
INLINE_CHARS = 120  # Longest value shown inline before it is summarised.
PREVIEW_LINES = 6  # Most output lines previewed from a command.
PREVIEW_CHARS = 600  # Most output characters previewed from a command.
RUNNING = ("●", Tokens.Text.WARNING)
FAILED = ("✕", Tokens.Text.ERROR)
DONE = ("✓", Tokens.Text.SUCCESS)


def render_tool_call(tool_call: ToolCall, output: ToolOutput | None) -> RenderableType:
    """The call's status, name and arguments, then its output once it has one; ``None``
    means it is still running."""
    tool = TOOLS.get(tool_call.tool_name, Tool())
    content = output.content if output else None
    failed = output is not None and (output.is_error or tool.failed(content))
    line = _call_line(tool_call, tool, error=failed, running=output is None)
    display = _display(output)
    if (result := tool.result(line, display, content)) is not None:
        return result
    return line + _result_line(display) if display else line


def _display(output: ToolOutput | None) -> str | None:
    """The output as text; a failure without any shows its error message."""
    if output is None:
        return None
    return output.display or (output.error_message if output.is_error else None)


def _call_line(tool_call: ToolCall, tool: Tool, *, running: bool, error: bool) -> Text:
    symbol, style = RUNNING if running else FAILED if error else DONE
    line = Text()
    line.append(f"{symbol} ", style=style)
    line.append(tool_call.tool_name, style=Tokens.Text.EMPHASIS)
    if tool_call.arguments and (arguments := tool.arguments(tool_call.arguments)):
        line.append(f" {arguments}", style=Tokens.Text.MUTED)
    return line


def _result_line(text: str) -> Text:
    return Text(f"\n{RESULT}{text}", style=Tokens.Text.MUTED)


def _arguments(arguments: Arguments) -> str:
    return " ".join(f"{key}={_value(value)}" for key, value in arguments.items())


def _no_result(line: Text, display: str | None, content: Content) -> RenderableType | None:  # noqa: ARG001
    return None


def _never_failed(content: Content) -> bool:  # noqa: ARG001
    return False


@dataclass(frozen=True, slots=True)
class Tool:
    """How a tool's call is shown; the defaults suit any tool."""

    arguments: Callable[[Arguments], str] = _arguments
    result: Callable[[Text, str | None, Content], RenderableType | None] = _no_result
    failed: Callable[[Content], bool] = _never_failed  # Failed by its result, not an error.


def _bash_arguments(arguments: Arguments) -> str:
    command = _inline(_text(arguments.get("command", "")))
    cwd = _text(arguments.get("cwd", "."))
    timeout = arguments.get("timeout_seconds", 30)
    return f"command={command} cwd={cwd} timeout={timeout}s"


def _bash_result(line: Text, display: str | None, content: Content) -> RenderableType | None:  # noqa: ARG001
    details = _bash_details(content)
    return None if details is None else line + _result_line(details)


def _bash_failed(content: Content) -> bool:
    exit_code = (content or {}).get("exit_code")
    return isinstance(exit_code, int) and exit_code != 0


def _bash_details(content: Content) -> str | None:
    """How the command went, then a preview of the output that matters most."""
    if not content:
        return None
    stdout = _text(content.get("stdout", ""))
    stderr = _text(content.get("stderr", ""))
    failed = _bash_failed(content)

    stderr_lines = _line_count(stderr)
    stderr_summary = "stderr empty" if stderr_lines == 0 else f"stderr {stderr_lines} lines"
    outcome = f"exit {content.get('exit_code')}" if failed else "succeeded"
    blocks = [f"{outcome}, stdout {_line_count(stdout)} lines, {stderr_summary}"]

    if failed and stderr:
        blocks.append(f"stderr:\n{_preview(stderr)}")
    elif stdout:
        blocks.append(f"stdout:\n{_preview(stdout, tail=not failed)}")
    elif stderr:
        blocks.append(f"stderr:\n{_preview(stderr)}")
    return f"\n{RESULT}".join(blocks)


def _edit_arguments(arguments: Arguments) -> str:
    return str(arguments.get("path", ""))


def _edit_result(line: Text, display: str | None, content: Content) -> RenderableType | None:  # noqa: ARG001
    if not display or not is_diff(display):
        return None
    summary = Text(f"{RESULT}{diff_summary(display)}", style=Tokens.Text.MUTED)
    return Group(line, summary, diff_blocks(display))


def _write_arguments(arguments: Arguments) -> str:
    path = arguments.get("path", "")
    return f"path={path} content={_value(arguments.get('content', ''))}"


TOOLS = {
    "bash": Tool(arguments=_bash_arguments, result=_bash_result, failed=_bash_failed),
    "edit_file": Tool(arguments=_edit_arguments, result=_edit_result),
    "write_file": Tool(arguments=_write_arguments),
}


def _value(value: object) -> str:
    """An argument value, summarised if it is long or spans lines."""
    if not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if "\n" in value or len(value) > INLINE_CHARS:
        return f"[{len(value)} chars, {_line_count(value)} lines]"
    return value


def _text(value: object) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _line_count(value: str) -> int:
    if not value:
        return 0
    return value.count("\n") + (0 if value.endswith("\n") else 1)


def _inline(value: str) -> str:
    """``value`` on one line, cut to ``INLINE_CHARS``."""
    normalized = " ".join(value.split())
    if len(normalized) <= INLINE_CHARS:
        return normalized
    return f"{normalized[: INLINE_CHARS - len(ELLIPSIS)].rstrip()}{ELLIPSIS}"


def _preview(value: str, *, tail: bool = False) -> str:
    """The first (or last) lines of ``value``, marked if anything was cut."""
    if not value:
        return ""
    lines = value.splitlines()
    cut_lines = len(lines) > PREVIEW_LINES
    preview = "\n".join(lines[-PREVIEW_LINES:] if tail else lines[:PREVIEW_LINES])
    cut_chars = len(preview) > PREVIEW_CHARS
    if cut_chars:
        preview = preview[-PREVIEW_CHARS:].lstrip() if tail else preview[:PREVIEW_CHARS].rstrip()
    if not (cut_lines or cut_chars):
        return preview
    marker = f"[truncated, {_line_count(value)} total lines]"
    return f"...\n{marker}\n{preview}" if tail else f"{preview}\n...\n{marker}"
