"""Rich to prompt_toolkit conversion utilities."""

import time
from io import StringIO
from typing import ClassVar

from prompt_toolkit.formatted_text import FormattedText, to_formatted_text
from prompt_toolkit.formatted_text.ansi import ANSI
from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import CodeBlock, Markdown
from rich.panel import Panel
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
            return self.convert(StyledMarkdown(message.content))
        if message.role == MessageRole.ASSISTANT:
            md = StyledMarkdown(message.content)
            panel = Panel(
                md,
                title="KODA",
                title_align="left",
                border_style="magenta",
            )
            return self.convert(panel)
        if message.role == MessageRole.TOOL:
            if message.tool_call:
                return self.render_tool_call(message.tool_call)
            return FormattedText([])
        return FormattedText([])

    def render_tool_call(self, tool_call: ToolCall) -> FormattedText:
        """Render a tool call indicator."""
        panel = Panel(
            f"[bold]{tool_call.tool_name}[/bold]",
            title="Tool Call",
            border_style="yellow",
        )
        return self.convert(panel)

    def render_streaming_content(self, content: str) -> FormattedText:
        """Render currently streaming content with cursor inside a panel."""
        md = StyledMarkdown(content + "\u2588")  # Blinking cursor block
        panel = Panel(
            md,
            title="KODA",
            title_align="left",
            border_style="magenta",
        )
        return self.convert(panel)

    def render_thinking_spinner(self, text: str = "Working...") -> FormattedText:
        """Render an animated thinking spinner."""
        frame_index = int(time.time() * 10) % len(SPINNER_FRAMES)
        frame = SPINNER_FRAMES[frame_index]

        rich_text = Text()
        rich_text.append(f"{frame} ", style="cyan")
        rich_text.append(text, style="dim italic")
        return self.convert(rich_text)

    def render_tool_spinner(self, tool_name: str) -> FormattedText:
        """Render a tool execution indicator."""
        text = Text()
        text.append("\u25cf ", style="yellow")  # Bullet point
        text.append(f"Running {tool_name}...", style="dim")
        return self.convert(text)
