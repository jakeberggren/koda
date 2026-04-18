import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from prompt_toolkit.formatted_text import FormattedText, merge_formatted_text, to_formatted_text
from rich.cells import cell_len
from rich.color import Color, ColorType
from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.markdown import CodeBlock, Heading, Markdown
from rich.segment import Segment
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from koda_service.types import ToolCall
from koda_tui.state import Message, MessageRole

Theme = Literal["dark", "light"]
type DiffBlockType = Literal["add", "del", "context"]

# Per-theme rendering constants
_THEME_COLORS = {
    "dark": {
        "code_theme": "ansi_dark",
        "user_fg": "#ffffff",
        "user_bg": "gray30",
        "diff_add_bg": "dark_green",
        "diff_del_bg": "dark_red",
        "quote_prefix": "magenta",
    },
    "light": {
        "code_theme": "ansi_light",
        "user_fg": "grey0",
        "user_bg": "grey89",
        "diff_add_bg": "#d4edda",
        "diff_del_bg": "#f8d7da",
        "quote_prefix": "magenta",
    },
}

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
CURSOR_BLOCK = "\u2588"
BASH_PREVIEW_LINES = 6
BASH_PREVIEW_CHARS = 600

# Rich standard color number → prompt_toolkit color name.
# Note: Rich "white" (7) maps to PT "ansigray", Rich "bright_white" (15) to PT "ansiwhite".
_STANDARD_COLOR_TO_PT = {
    0: "ansiblack",
    1: "ansired",
    2: "ansigreen",
    3: "ansiyellow",
    4: "ansiblue",
    5: "ansimagenta",
    6: "ansicyan",
    7: "ansigray",
    8: "ansibrightblack",
    9: "ansibrightred",
    10: "ansibrightgreen",
    11: "ansibrightyellow",
    12: "ansibrightblue",
    13: "ansibrightmagenta",
    14: "ansibrightcyan",
    15: "ansiwhite",
}


def _rich_color_to_pt(color: Color | None) -> str:
    """Convert a Rich Color to a prompt_toolkit color string."""
    if color is None or color.is_default:
        return ""
    if color.type == ColorType.STANDARD and color.number is not None:
        return _STANDARD_COLOR_TO_PT.get(color.number, "")
    if color.triplet is not None:
        r, g, b = color.triplet
        return f"#{r:02x}{g:02x}{b:02x}"
    if color.type == ColorType.EIGHT_BIT:
        triplet = color.get_truecolor()
        return f"#{triplet.red:02x}{triplet.green:02x}{triplet.blue:02x}"
    return ""


_RICH_ATTR_TO_PT = (
    ("bold", "bold"),
    ("dim", "dim"),
    ("italic", "italic"),
    ("underline", "underline"),
    ("blink", "blink"),
    ("blink2", "blink"),
    ("reverse", "reverse"),
    ("conceal", "hidden"),
    ("strike", "strike"),
)


def _rich_attrs_to_pt(style: Style) -> list[str]:
    """Extract active boolean attributes from a Rich Style as PT keywords."""
    return [pt for attr, pt in _RICH_ATTR_TO_PT if getattr(style, attr)]


def _rich_style_to_pt(style: Style | None) -> str:
    """Convert a Rich Style to a prompt_toolkit style string."""
    if style is None or not str(style):
        return ""

    parts: list[str] = []

    fg = _rich_color_to_pt(style.color)
    if fg:
        parts.append(fg)

    bg = _rich_color_to_pt(style.bgcolor)
    if bg:
        parts.append(f"bg:{bg}")

    parts.extend(_rich_attrs_to_pt(style))

    return " ".join(parts)


DIFF_HEADER_FILENAME_RE = re.compile(r"^---\s+\S+?([^/\s]+)$", re.MULTILINE)
DIFF_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
DIFF_ADDITION_RE = re.compile(r"^\+(?!\+\+)", re.MULTILINE)
DIFF_DELETION_RE = re.compile(r"^-(?!--)", re.MULTILINE)


@dataclass
class DiffBlockAccumulator:
    """Accumulates diff lines and renders them as syntax-highlighted blocks."""

    lexer: str
    code_theme: str
    diff_add_bg: str
    diff_del_bg: str
    renderables: list = field(default_factory=list)
    block_type: DiffBlockType | None = None
    lines: list[str] = field(default_factory=list)
    start_line: int | None = None

    def flush(self) -> None:
        """Flush accumulated lines as a Syntax block."""
        if not self.lines:
            return

        bg_by_type: dict[DiffBlockType, str] = {
            "add": self.diff_add_bg,
            "del": self.diff_del_bg,
            "context": "default",
        }
        bg = "default" if self.block_type is None else bg_by_type[self.block_type]
        self.renderables.append(
            Syntax(
                "\n".join(self.lines),
                self.lexer,
                theme=self.code_theme,
                background_color=bg,
                line_numbers=True,
                start_line=self.start_line or 1,
            )
        )
        self.lines = []
        self.block_type = None
        self.start_line = None

    def add_line(self, line: str, line_type: DiffBlockType, start: int | None) -> None:
        """Add a line, flushing first if the type changes."""
        if self.block_type != line_type:
            self.flush()
            self.block_type = line_type
            self.start_line = start
        self.lines.append(line)


def _create_themed_markdown(code_theme: str) -> type:
    """Create a Markdown subclass with themed elements."""

    class _CodeBlock(CodeBlock):
        def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
            code = str(self.text).rstrip()
            yield Syntax(code, self.lexer_name, theme=code_theme, background_color="default")

    class _Heading(Heading):
        def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
            self.text.justify = "left"
            yield self.text

    class _Markdown(Markdown):
        elements: ClassVar = {
            **Markdown.elements,
            "fence": _CodeBlock,
            "heading_open": _Heading,
        }

    return _Markdown


class QuotedContent:
    """Wraps a renderable with quoted prefix and full-width background."""

    def __init__(self, renderable, *, bg_color: str, prefix_color: str) -> None:
        self.renderable = renderable
        self._bg_style = Style(bgcolor=bg_color)
        self._prefix_style = Style(color=prefix_color)

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        render_options = options.update(width=options.max_width - 2)
        lines = console.render_lines(self.renderable, render_options)
        new_line = Segment("\n")

        for line in lines:
            yield Segment("▌ ", self._prefix_style)
            line_width = 2
            for seg in line:
                if seg.text:
                    style = seg.style + self._bg_style if seg.style else self._bg_style
                    yield Segment(seg.text, style)
                    line_width += cell_len(seg.text)
            padding = options.max_width - line_width
            if padding > 0:
                yield Segment(" " * padding, self._bg_style)
            yield new_line


class MessageRenderer:
    """
    Renders messages, tool calls, and streaming content as FormattedText.

    Uses Rich as the rendering engine and converts the output to
    prompt_toolkit FormattedText for display in TUI components.
    """

    def __init__(self, width: int = 80, theme: Theme = "dark") -> None:
        self._width = width
        self._colors = _THEME_COLORS[theme]
        self._markdown_cls = _create_themed_markdown(self._colors["code_theme"])

    def set_width(self, width: int) -> None:
        """Update the rendering width."""
        self._width = width

    def set_theme(self, theme: Theme) -> None:
        """Switch the rendering theme."""
        self._colors = _THEME_COLORS.get(theme, _THEME_COLORS["dark"])
        self._markdown_cls = _create_themed_markdown(self._colors["code_theme"])

    def convert(self, renderable) -> FormattedText:
        """Convert Rich renderable directly to prompt_toolkit FormattedText."""
        console = Console(width=self._width, force_terminal=True, no_color=False)
        segments = console.render(renderable)
        cropped = Segment.split_and_crop_lines(segments, self._width, pad=False)

        result: list[tuple[str, str]] = []
        for line in cropped:
            result.extend(
                (_rich_style_to_pt(seg.style), seg.text)
                for seg in line
                if not seg.control and seg.text
            )

        # Strip leading newlines (Rich Markdown may emit them)
        while result and result[0][1] == "\n":
            result.pop(0)

        return FormattedText(result)

    def _get_lexer_from_diff(self, diff: str) -> str:
        """Extract lexer from diff header filename."""
        match = DIFF_HEADER_FILENAME_RE.search(diff)
        if match:
            filename = match.group(1)
            return Syntax.guess_lexer(filename)
        return "text"

    def _render_diff(self, diff: str) -> Group:  # noqa: C901 - allow complex
        """Render a unified diff with syntax highlighting and colored backgrounds."""
        accumulator = DiffBlockAccumulator(
            lexer=self._get_lexer_from_diff(diff),
            code_theme=self._colors["code_theme"],
            diff_add_bg=self._colors["diff_add_bg"],
            diff_del_bg=self._colors["diff_del_bg"],
        )
        old_line: int | None = None
        new_line: int | None = None

        for line in diff.splitlines():
            if line.startswith("@@"):
                accumulator.flush()
                if match := DIFF_HUNK_RE.match(line):
                    old_line, new_line = int(match.group(1)), int(match.group(2))
            elif line.startswith(("+++", "---")):
                continue
            elif line.startswith("+"):
                accumulator.add_line(line, "add", new_line)
                new_line = new_line + 1 if new_line else None
            elif line.startswith("-"):
                accumulator.add_line(line, "del", old_line)
                old_line = old_line + 1 if old_line else None
            else:
                accumulator.add_line(line, "context", new_line)
                new_line = new_line + 1 if new_line else None
                old_line = old_line + 1 if old_line else None

        accumulator.flush()
        return Group(*accumulator.renderables)

    def _get_tool_result_display(self, message: Message) -> str | None:
        result_display = message.tool_result_display
        if not result_display and message.tool_error and message.tool_error_message:
            return message.tool_error_message
        return result_display

    @staticmethod
    def _combine_formatted_text(*fragments: FormattedText) -> FormattedText:
        return to_formatted_text(merge_formatted_text(fragments))

    @staticmethod
    def _stringify_tool_value(value: object) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _line_count(value: str) -> int:
        if not value:
            return 0
        return value.count("\n") + (0 if value.endswith("\n") else 1)

    def _preview_text(
        self,
        value: str,
        *,
        max_lines: int = BASH_PREVIEW_LINES,
        max_chars: int = BASH_PREVIEW_CHARS,
        tail: bool = False,
    ) -> str:
        if not value:
            return ""

        lines = value.splitlines()
        truncated_by_lines = len(lines) > max_lines
        preview_lines = lines[-max_lines:] if tail else lines[:max_lines]
        preview = "\n".join(preview_lines)
        truncated_by_chars = len(preview) > max_chars
        if truncated_by_chars:
            preview = preview[-max_chars:].lstrip() if tail else preview[:max_chars].rstrip()

        if truncated_by_lines or truncated_by_chars:
            total_lines = self._line_count(value)
            marker = f"[truncated, {total_lines} total lines]"
            preview = f"{marker}\n{preview}" if tail else f"{preview}\n{marker}"
        return preview

    def _format_bash_args(self, arguments: dict[str, object]) -> str:
        cwd = self._stringify_tool_value(arguments.get("cwd", "."))
        timeout = arguments.get("timeout_seconds", 30)
        command = self._stringify_tool_value(arguments.get("command", ""))
        return f"command={command} cwd={cwd} timeout={timeout}s"

    def _bash_result_details(self, content: dict[str, Any] | None) -> str | None:
        if not content:
            return None

        stdout = self._stringify_tool_value(content.get("stdout", ""))
        stderr = self._stringify_tool_value(content.get("stderr", ""))
        exit_code = content.get("exit_code")
        failed = self._bash_command_failed(content)

        stdout_lines = self._line_count(stdout)
        stderr_lines = self._line_count(stderr)
        stderr_summary = "stderr empty" if stderr_lines == 0 else f"stderr {stderr_lines} lines"
        summary = (
            f"exit {exit_code}, stdout {stdout_lines} lines, {stderr_summary}"
            if failed
            else f"succeeded, stdout {stdout_lines} lines, {stderr_summary}"
        )

        blocks = [summary]
        if stderr:
            blocks.append(f"stderr:\n{self._preview_text(stderr)}")
        elif stdout:
            blocks.append(f"stdout:\n{self._preview_text(stdout, tail=not failed)}")

        return "\n  \u2514 ".join(blocks)

    @staticmethod
    def _bash_command_failed(content: dict[str, Any] | None) -> bool:
        if not content:
            return False
        exit_code = content.get("exit_code")
        return isinstance(exit_code, int) and exit_code != 0

    @staticmethod
    def _tool_status_indicator(*, running: bool, error: bool) -> tuple[str, str]:
        """Return (symbol, style) for the tool call status."""
        if running:
            return ("\u25cf ", "yellow")
        if error:
            return ("\u2715 ", "red")
        return ("\u2713 ", "green")

    def _render_thinking_markdown(
        self,
        content: str,
        *,
        add_spacing: bool = False,
    ) -> FormattedText:
        fragment = self.convert(self._markdown_cls(content, style=Style(dim=True, italic=True)))
        if not add_spacing:
            return fragment
        return self._combine_formatted_text(fragment, FormattedText([("", "\n")]))

    def _render_assistant_message(self, message: Message) -> FormattedText:
        fragments: list[FormattedText] = []
        if message.thinking_content:
            fragments.append(
                self._render_thinking_markdown(
                    message.thinking_content,
                    add_spacing=bool(message.content),
                )
            )
        if message.content:
            fragments.append(self.convert(self._markdown_cls(message.content)))

        if not fragments:
            return FormattedText([])
        if len(fragments) == 1:
            return fragments[0]
        return self._combine_formatted_text(*fragments)

    def render_message(self, message: Message) -> FormattedText:
        """Render a single message to FormattedText."""
        match message.role:
            case MessageRole.USER:
                user_content = self._markdown_cls(
                    message.content,
                    style=Style(
                        color=self._colors["user_fg"],
                        bgcolor=self._colors["user_bg"],
                    ),
                )
                quoted_content = QuotedContent(
                    user_content,
                    bg_color=self._colors["user_bg"],
                    prefix_color=self._colors["quote_prefix"],
                )
                return self.convert(quoted_content)
            case MessageRole.ASSISTANT:
                return self._render_assistant_message(message)
            case MessageRole.TOOL if message.tool_call:
                return self.render_tool_call(
                    message.tool_call,
                    running=message.tool_running,
                    error=message.tool_error,
                    result_display=self._get_tool_result_display(message),
                    result_content=message.tool_result_content,
                )
            case MessageRole.TOOL:
                return FormattedText([])

    def _summarize_string(self, value: str, max_inline_chars: int = 120) -> str:
        if "\n" in value or len(value) > max_inline_chars:
            line_count = value.count("\n") + (1 if value and not value.endswith("\n") else 0)
            return f"[{len(value)} chars, {line_count} lines]"
        return value

    def _format_tool_value(self, value: object) -> str:
        if isinstance(value, str):
            return self._summarize_string(value)
        return json.dumps(value, ensure_ascii=False)

    def _format_write_file_args(self, arguments: dict[str, object]) -> str:
        path = arguments.get("path", "")
        content = arguments.get("content", "")
        parts = [f"path={path}", f"content={self._format_tool_value(content)}"]
        return " ".join(parts)

    def _format_edit_file_args(self, arguments: dict[str, object]) -> str:
        path = arguments.get("path", "")
        return str(path)

    def _summarize_diff(self, diff: str) -> str:
        """Summarize a diff with addition/deletion counts and format accordingly."""
        additions = len(DIFF_ADDITION_RE.findall(diff))
        deletions = len(DIFF_DELETION_RE.findall(diff))

        additions_str = f"{additions} addition" if additions == 1 else f"{additions} additions"
        deletions_str = f"{deletions} deletion" if deletions == 1 else f"{deletions} deletions"
        comma = ", " if additions > 0 else ""

        return f"{additions_str}{comma}{deletions_str}"

    def _format_tool_args(self, tool_name: str, arguments: dict[str, object]) -> str:
        """Format tool arguments for display."""
        if not arguments:
            return ""

        if tool_name == "write_file":
            return self._format_write_file_args(arguments)

        if tool_name == "edit_file":
            return self._format_edit_file_args(arguments)

        if tool_name == "bash":
            return self._format_bash_args(arguments)

        parts = [f"{key}={self._format_tool_value(value)}" for key, value in arguments.items()]
        return " ".join(parts)

    @staticmethod
    def _tool_status_indicator(*, running: bool, error: bool) -> tuple[str, str]:
        """Return (symbol, style) for the tool call status."""
        if running:
            return ("\u25cf ", "yellow")
        if error:
            return ("\u2715 ", "red")
        return ("\u2713 ", "green")

    def _build_tool_call_text(
        self,
        tool_call: ToolCall,
        *,
        running: bool,
        error: bool,
    ) -> Text:
        """Build the base rich text for a tool call."""
        symbol, style = self._tool_status_indicator(running=running, error=error)
        text = Text()
        text.append(symbol, style=style)
        text.append(tool_call.tool_name, style="italic")

        arguments = self._format_tool_args(tool_call.tool_name, tool_call.arguments)
        if arguments:
            text.append(f" {arguments}", style="dim")
        return text

    def _render_bash_tool_result(
        self,
        text: Text,
        result_content: dict[str, Any] | None,
    ) -> FormattedText | None:
        """Render bash result details when available."""
        bash_details = self._bash_result_details(result_content)
        if not bash_details:
            return None

        text.append(f"\n  └ {bash_details}", style="dim")
        return self.convert(text)

    def _render_tool_result_display(
        self,
        tool_call: ToolCall,
        text: Text,
        result_display: str | None,
    ) -> FormattedText | None:
        """Render a tool result display when present."""
        if not result_display:
            return None

        if tool_call.tool_name == "edit_file" and result_display.startswith("---"):
            summary = self._summarize_diff(result_display)
            summary_text = Text(f"  └ {summary}", style="dim")
            diff_renderable = self._render_diff(result_display)
            return self.convert(Group(text, summary_text, diff_renderable))

        text.append(f"\n  └ {result_display}", style="dim")
        return self.convert(text)

    def render_tool_call(
        self,
        tool_call: ToolCall,
        *,
        running: bool = False,
        error: bool = False,
        result_display: str | None = None,
        result_content: dict[str, Any] | None = None,
    ) -> FormattedText:
        """Render a tool call indicator with optional result display."""
        effective_error = error or (
            tool_call.tool_name == "bash" and self._bash_command_failed(result_content)
        )
        text = self._build_tool_call_text(tool_call, running=running, error=effective_error)

        if tool_call.tool_name == "bash":
            bash_result = self._render_bash_tool_result(text, result_content)
            if bash_result is not None:
                return bash_result

        rendered_result = self._render_tool_result_display(tool_call, text, result_display)
        if rendered_result is not None:
            return rendered_result

        return self.convert(text)

    def render_streaming_content(self, content: str) -> FormattedText:
        """Render currently streaming content with cursor inside a panel."""
        md = self._markdown_cls(content + CURSOR_BLOCK)
        return self.convert(md)

    def render_thinking_content(self, content: str) -> FormattedText:
        """Render currently streaming thinking content."""
        return self._render_thinking_markdown(content + CURSOR_BLOCK)

    def render_thinking_spinner(self, text: str = "Working... (esc to interrupt)") -> FormattedText:
        """Render an animated thinking spinner."""
        frame_index = int(time.time() * 10) % len(SPINNER_FRAMES)
        frame = SPINNER_FRAMES[frame_index]

        rich_text = Text()
        rich_text.append(f"{frame} ", style="cyan")
        rich_text.append(text, style="dim italic")
        return self.convert(rich_text)
