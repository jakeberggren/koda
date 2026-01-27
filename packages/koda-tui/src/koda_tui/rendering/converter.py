"""Rich to prompt_toolkit conversion utilities."""

import json
import re
import time
from dataclasses import dataclass, field
from io import StringIO
from typing import ClassVar

from prompt_toolkit.formatted_text import FormattedText, to_formatted_text
from prompt_toolkit.formatted_text.ansi import ANSI
from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.markdown import BlockQuote, CodeBlock, Heading, Markdown
from rich.segment import Segment
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme

from koda.tools import ToolCall
from koda_tui.app.state import Message, MessageRole

CODE_THEME = "ansi_dark"
DIFF_ADD_BG = "dark_green"
DIFF_DEL_BG = "dark_red"
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

DIFF_HEADER_FILENAME_RE = re.compile(r"^---\s+\S+?([^/\s]+)$", re.MULTILINE)
DIFF_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
DIFF_ADDITION_RE = re.compile(r"^\+(?!\+\+)", re.MULTILINE)
DIFF_DELETION_RE = re.compile(r"^-(?!--)", re.MULTILINE)

MARKDOWN_THEME = Theme(
    {
        "markdown.hr": "white",
        "markdown.list": "white",
        "markdown.item.number": "white",
        "markdown.item.bullet": "white",
    }
)


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

        bg = {"add": DIFF_ADD_BG, "del": DIFF_DEL_BG}.get(self.block_type, "default")
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
            line_numbers=True,
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


class BlueBlockQuote(BlockQuote):
    """Block quote with blue styling."""

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        # Render children and apply blue color via ANSI escape directly
        render_options = options.update(width=options.max_width - 4)
        lines = console.render_lines(self.elements, render_options)
        new_line = Segment("\n")
        # Use ANSI 34 directly for blue (matches prompt_toolkit's ansiblue)
        blue = Segment("\x1b[34m")
        reset = Segment("\x1b[0m")
        for line in lines:
            yield blue
            yield Segment("▌ ")
            for seg in line:
                # Strip existing styles from segment text
                yield Segment(seg.text)
            yield reset
            yield new_line


class UserMarkdown(Markdown):
    """Markdown for user messages with blue blockquotes."""

    elements: ClassVar = {
        **Markdown.elements,
        "fence": NoBackgroundCodeBlock,
        "heading_open": LeftAlignedHeading,
        "blockquote_open": BlueBlockQuote,
    }


class RichToPromptToolkit:
    """Converts Rich renderable objects to prompt_toolkit FormattedText."""

    def __init__(self, width: int = 80) -> None:
        self._width = width

    def set_width(self, width: int) -> None:
        """Update the rendering width."""
        self._width = width

    def _render_to_ansi(self, renderable) -> str:
        """Render a Rich object to ANSI string."""
        buffer = StringIO()
        console = Console(
            file=buffer,
            force_terminal=True,
            width=self._width,
            no_color=False,
            theme=MARKDOWN_THEME,
        )
        console.print(renderable, end="")
        return buffer.getvalue().lstrip("\n")

    def convert(self, renderable) -> FormattedText:
        """Convert Rich renderable to prompt_toolkit FormattedText."""
        ansi_str = self._render_to_ansi(renderable)
        return to_formatted_text(ANSI(ansi_str))

    def _quote_user_content(self, content: str) -> str:
        lines = content.split("\n")
        quoted_lines = [f"> {line}" if line else ">" for line in lines]
        return "\n".join(quoted_lines)

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
                return self.convert(UserMarkdown(self._quote_user_content(message.content)))
            case MessageRole.ASSISTANT:
                return self.convert(StyledMarkdown(message.content))
            case MessageRole.TOOL:
                if message.tool_call:
                    return self.render_tool_call(
                        message.tool_call,
                        running=message.tool_running,
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
        comma = ", " if additions > 0 and deletions > 0 else ""

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

    def render_tool_call(
        self,
        tool_call: ToolCall,
        *,
        running: bool = False,
        result_display: str | None = None,
    ) -> FormattedText:
        """Render a tool call indicator with optional result display."""
        text = Text()
        text.append("\u25cf ", style="yellow" if running else "green")  # bullet
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
