"""Rich to prompt_toolkit conversion utilities."""

import time
from io import StringIO

from prompt_toolkit.formatted_text import FormattedText, to_formatted_text
from prompt_toolkit.formatted_text.ansi import ANSI
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from koda.tools import ToolCall
from koda_tui.app.state import Message, MessageRole

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


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
            text = Text()
            text.append(message.content)
            return self.convert(text)
        if message.role == MessageRole.ASSISTANT:
            text = Text()
            text.append(message.content)
            return self.convert(text)
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
            expand=False,
        )
        return self.convert(panel)

    def render_streaming_content(self, content: str) -> FormattedText:
        """Render currently streaming content with cursor."""
        text = Text()
        text.append(content)
        text.append("\u2588", style="blink")  # Blinking cursor block
        return self.convert(text)

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
