"""Rich to prompt_toolkit conversion utilities."""

import json
import time
from io import StringIO
from typing import ClassVar

from prompt_toolkit.formatted_text import FormattedText, to_formatted_text
from prompt_toolkit.formatted_text.ansi import ANSI
from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import BlockQuote, CodeBlock, Heading, Markdown
from rich.segment import Segment
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme

from koda.tools import ToolCall
from koda_tui.app.state import Message, MessageRole

CODE_THEME = "dracula"
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
MARKDOWN_THEME = Theme(
    {
        "markdown.hr": "white",
        "markdown.list": "white",
        "markdown.item.number": "white",
        "markdown.item.bullet": "white",
    }
)


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

    def _format_tool_args(self, tool_name: str, arguments: dict[str, object]) -> str:
        """Format tool arguments for display."""
        if not arguments:
            return ""

        if tool_name == "write_file":
            return self._format_write_file_args(arguments)

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
