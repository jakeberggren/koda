import json
import re
import time
from dataclasses import dataclass, field
from typing import ClassVar

from prompt_toolkit.formatted_text import FormattedText
from rich.cells import cell_len
from rich.color import Color, ColorType
from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.markdown import CodeBlock, Heading, Markdown
from rich.segment import Segment
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from koda.tools import ToolCall
from koda_tui.state import Message, MessageRole

CODE_THEME = "ansi_dark"

WHITE = "#ffffff"
GREY30 = "#4e4e4e"
MAGENTA = "magenta"
DARK_GREEN = "#005f00"
DARK_RED = "#870000"

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

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
    renderables: list = field(default_factory=list)
    block_type: str | None = None
    lines: list[str] = field(default_factory=list)
    start_line: int | None = None

    def flush(self) -> None:
        """Flush accumulated lines as a Syntax block."""
        if not self.lines:
            return

        bg = {"add": DARK_GREEN, "del": DARK_RED}.get(self.block_type, "default")
        self.renderables.append(
            Syntax(
                "\n".join(self.lines),
                self.lexer,
                theme=CODE_THEME,
                background_color=bg,
                line_numbers=True,
                start_line=self.start_line or 1,
            )
        )
        self.lines = []
        self.block_type = None
        self.start_line = None

    def add_line(self, line: str, line_type: str, start: int | None) -> None:
        """Add a line, flushing first if the type changes."""
        if self.block_type != line_type:
            self.flush()
            self.block_type = line_type
            self.start_line = start
        self.lines.append(line)


class NoBackgroundCodeBlock(CodeBlock):
    """Code block without background color."""

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        code = str(self.text).rstrip()
        yield Syntax(
            code,
            self.lexer_name,
            theme=CODE_THEME,
            background_color="default",
        )


class LeftAlignedHeading(Heading):
    """Markdown heading rendered with left alignment."""

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        self.text.justify = "left"
        yield self.text


class StyledMarkdown(Markdown):
    """Markdown with code blocks without background."""

    elements: ClassVar = {
        **Markdown.elements,
        "fence": NoBackgroundCodeBlock,
        "heading_open": LeftAlignedHeading,
    }


class QuotedContent:
    """Wraps a renderable with a magenta quote prefix and full-width background."""

    PREFIX_STYLE = Style(color=MAGENTA)
    BG_STYLE = Style(bgcolor=GREY30)

    def __init__(self, renderable) -> None:
        self.renderable = renderable

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        render_options = options.update(width=options.max_width - 2)
        lines = console.render_lines(self.renderable, render_options)
        new_line = Segment("\n")

        for line in lines:
            yield Segment("▌ ", self.PREFIX_STYLE)
            line_width = 2
            for seg in line:
                if seg.text:
                    style = seg.style + self.BG_STYLE if seg.style else self.BG_STYLE
                    yield Segment(seg.text, style)
                    line_width += cell_len(seg.text)
            padding = options.max_width - line_width
            if padding > 0:
                yield Segment(" " * padding, self.BG_STYLE)
            yield new_line


class MessageRenderer:
    """
    Renders messages, tool calls, and streaming content as FormattedText.

    Uses Rich as the rendering engine and converts the output to
    prompt_toolkit FormattedText for display in TUI components.
    """

    def __init__(self, width: int = 80) -> None:
        self._width = width

    def set_width(self, width: int) -> None:
        """Update the rendering width."""
        self._width = width

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
        accumulator = DiffBlockAccumulator(lexer=self._get_lexer_from_diff(diff))
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

    def render_message(self, message: Message) -> FormattedText:
        """Render a single message to FormattedText."""
        match message.role:
            case MessageRole.USER:
                return self.convert(
                    QuotedContent(
                        StyledMarkdown(message.content, style=Style(color=WHITE, bgcolor=GREY30))
                    )
                )
            case MessageRole.ASSISTANT:
                return self.convert(StyledMarkdown(message.content))
            case MessageRole.TOOL:
                if message.tool_call:
                    return self.render_tool_call(
                        message.tool_call,
                        running=message.tool_running,
                        error=message.tool_error,
                        result_display=message.tool_result_display,
                    )
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

    def render_tool_call(
        self,
        tool_call: ToolCall,
        *,
        running: bool = False,
        error: bool = False,
        result_display: str | None = None,
    ) -> FormattedText:
        """Render a tool call indicator with optional result display."""
        symbol, style = self._tool_status_indicator(running=running, error=error)
        text = Text()
        text.append(symbol, style=style)
        text.append(tool_call.tool_name, style="italic")

        arguments = self._format_tool_args(tool_call.tool_name, tool_call.arguments)
        if arguments:
            text.append(f" {arguments}", style="dim")

        if result_display:
            if tool_call.tool_name == "edit_file" and result_display.startswith("---"):
                # Render diff with syntax highlighting
                summary = self._summarize_diff(result_display)
                summary_text = Text(f"  └ {summary}", style="dim")
                diff_renderable = self._render_diff(result_display)
                return self.convert(Group(text, summary_text, diff_renderable))
            text.append(f"\n  └ {result_display}", style="dim")

        return self.convert(text)

    def render_streaming_content(self, content: str) -> FormattedText:
        """Render currently streaming content with cursor inside a panel."""
        md = StyledMarkdown(content + "\u2588")  # Blinking cursor block
        return self.convert(md)

    def render_thinking_spinner(self, text: str = "Working... (esc to interrupt)") -> FormattedText:
        """Render an animated thinking spinner."""
        frame_index = int(time.time() * 10) % len(SPINNER_FRAMES)
        frame = SPINNER_FRAMES[frame_index]

        rich_text = Text()
        rich_text.append(f"{frame} ", style="cyan")
        rich_text.append(text, style="dim italic")
        return self.convert(rich_text)
