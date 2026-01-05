from contextlib import contextmanager
from typing import Protocol

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

from koda.tools import ToolCall


class Renderer(Protocol):
    """Protocol for rendering output to the user."""

    def print(self, message: str) -> None:
        """Print a message."""
        ...

    def print_assistant(self, message: str) -> None:
        """Print an assistant message."""
        ...

    def print_error(self, message: str) -> None:
        """Print an error message."""
        ...

    def print_info(self, message: str) -> None:
        """Print an info message."""
        ...

    def print_tool_call(self, tool_call: ToolCall) -> None:
        """Print a tool call."""
        ...

    def write(self, text: str) -> None:
        """Write text without a newline (for streaming)."""
        ...

    def flush(self) -> None:
        """Flush any buffered output and add final newline."""
        ...

    @contextmanager
    def thinking_spinner(self):
        """Context manager for showing a thinking spinner."""
        ...


class RichRenderer(Renderer):
    """Renderer using rich for terminal output."""

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()

    def print(self, message: str) -> None:
        self._console.print(message)

    def print_assistant(self, message: str) -> None:
        self._console.print(f"[bold]Koda:[/bold] {message}\n")

    def print_error(self, message: str) -> None:
        self._console.print(f"[red]Error: {message}[/red]")

    def print_info(self, message: str) -> None:
        self._console.print(f"[dim]{message}[/dim]")

    def print_tool_call(self, tool_call: ToolCall) -> None:
        self._console.print(f"[bold]Tool call:[/bold] {tool_call.tool_name}\n")

    def write(self, text: str) -> None:
        self._console.print(text, end="")

    def flush(self) -> None:
        self._console.print("\n")

    @contextmanager
    def thinking_spinner(self):
        """Show a spinner while thinking."""
        with Live(
            Spinner("dots", text="Working..."),
            console=self._console,
            transient=True,
        ) as live:
            yield live
