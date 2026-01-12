"""Rich to prompt_toolkit conversion utilities."""

import time
from io import StringIO
from typing import ClassVar

from prompt_toolkit.formatted_text import FormattedText, to_formatted_text
from prompt_toolkit.formatted_text.ansi import ANSI
from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import BlockQuote, CodeBlock, Markdown
from rich.segment import Segment
from rich.syntax import Syntax
from rich.text import Text

from koda.tools import ToolCall
from koda_tui.app.state import Message, MessageRole

CODE_THEME = "dracula"
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


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


class StyledMarkdown(Markdown):
    """Markdown with code blocks without background."""

    elements: ClassVar = {**Markdown.elements, "fence": NoBackgroundCodeBlock}


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
        )
        console.print(renderable, end="")
        return buffer.getvalue()

    def convert(self, renderable) -> FormattedText:
        """Convert Rich renderable to prompt_toolkit FormattedText."""
        ansi_str = self._render_to_ansi(renderable)
        return to_formatted_text(ANSI(ansi_str))

    def render_message(self, message: Message) -> FormattedText:
        """Render a single message to FormattedText."""
        if message.role == MessageRole.USER:
            return self.convert(UserMarkdown("> " + message.content))
        if message.role == MessageRole.ASSISTANT:
            return self.convert(StyledMarkdown(message.content))
        if message.role == MessageRole.TOOL:
            if message.tool_call:
                return self.render_tool_call(message.tool_call, running=message.tool_running)
            return FormattedText([])
        return FormattedText([])

    def render_tool_call(self, tool_call: ToolCall, *, running: bool = False) -> FormattedText:
        """Render a tool call indicator."""
        text = Text()
        bullet_style = "yellow" if running else "green"
        text.append("\u25cf ", style=bullet_style)
        text.append(tool_call.tool_name, style="italic")
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
