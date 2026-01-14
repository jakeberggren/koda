"""Command palette component for Koda TUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import FuzzyWordCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    BufferControl,
    FormattedTextControl,
    HSplit,
    VSplit,
    Window,
    WindowAlign,
)
from prompt_toolkit.widgets import Box

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.key_binding import KeyPressEvent

COMMAND_PALETTE_TITLE = "Commands"
COMMAND_PALETTE_ITEM_SELECTED_PREFIX = "- "
COMMAND_PALETTE_ITEM_UNSELECTED_PREFIX = "  "
COMMAND_PALETTE_SEARCH_INPUT_HEIGHT = 1
COMMAND_PALETTE_LIST_HEIGHT = 10
COMMAND_PALETTE_BOX_PADDING_LEFT = 2
COMMAND_PALETTE_BOX_PADDING_RIGHT = 2
COMMAND_PALETTE_BOX_PADDING_TOP = 1
COMMAND_PALETTE_BOX_PADDING_BOTTOM = 1
COMMAND_PALLETE_SEPARATOR_HEIGHT = 1


@dataclass
class Command:
    """A command that can be executed from the palette."""

    label: str
    handler: Callable[[], None]
    description: str = ""


class CommandPalette:
    """Floating command palette with fuzzy search."""

    def __init__(
        self,
        commands: list[Command],
        on_close: Callable[[], None],
        height: int = COMMAND_PALETTE_LIST_HEIGHT,
    ) -> None:
        self.commands = commands
        self.on_close = on_close
        self.selected_index = 0
        self._filtered_commands: list[Command] = list(commands)
        self._height = height

        # Create fuzzy completer from command labels
        command_labels = [cmd.label for cmd in commands]
        completer = FuzzyWordCompleter(command_labels)

        # Search buffer
        self.search_buffer = Buffer(
            completer=completer,
            complete_while_typing=True,
            on_text_changed=self._on_search_changed,
        )

        # Key bindings local to the palette
        self._kb = self._create_keybindings()

        # Build the container
        self._container = self._build_container()

    def _on_search_changed(self, buffer: Buffer) -> None:
        """Filter commands based on search text."""
        search_text = buffer.text.lower()
        if not search_text:
            self._filtered_commands = list(self.commands)
        else:
            self._filtered_commands = [
                cmd for cmd in self.commands if search_text in cmd.label.lower()
            ]
        # Reset selection when filter changes
        self.selected_index = 0

    def _move_selection(self, delta: int) -> None:
        """Move selection by delta, wrapping around."""
        if self._filtered_commands:
            self.selected_index = (self.selected_index + delta) % len(self._filtered_commands)

    def _execute_selected(self) -> None:
        """Execute the currently selected command."""
        if self._filtered_commands:
            cmd = self._filtered_commands[self.selected_index]
            self.on_close()
            cmd.handler()

    def _create_keybindings(self) -> KeyBindings:
        """Create key bindings for palette navigation."""
        kb = KeyBindings()

        @kb.add(Keys.Escape, eager=True)
        def _close(_event: KeyPressEvent) -> None:
            self.on_close()

        @kb.add(Keys.Enter)
        def _select(_event: KeyPressEvent) -> None:
            self._execute_selected()

        @kb.add(Keys.Up)
        def _move_up(_event: KeyPressEvent) -> None:
            self._move_selection(-1)

        @kb.add(Keys.Down)
        def _move_down(_event: KeyPressEvent) -> None:
            self._move_selection(1)

        return kb

    def _get_command_list_text(self) -> list[tuple[str, str]]:
        """Generate formatted text for the command list."""
        result: list[tuple[str, str]] = []

        for i, cmd in enumerate(self._filtered_commands):
            is_selected = i == self.selected_index
            style = "class:palette.selected" if is_selected else "class:palette.item"
            prefix = (
                COMMAND_PALETTE_ITEM_SELECTED_PREFIX
                if is_selected
                else COMMAND_PALETTE_ITEM_UNSELECTED_PREFIX
            )
            result.append((style, f"{prefix}{cmd.label}\n"))

        if not self._filtered_commands:
            result.append(("class:palette.empty", "  No matching commands\n"))

        return result

    def _build_container(self) -> Box:
        """Build the palette UI container."""
        # Title
        title = Window(
            content=FormattedTextControl(text=[("class:palette.title", COMMAND_PALETTE_TITLE)]),
            height=1,
            align=WindowAlign.CENTER,
            dont_extend_height=True,
        )

        # Search input row
        search_prompt = Window(
            content=FormattedTextControl(text=[("class:palette.prompt", "❯ ")]),  # noqa: RUF001 - allow confusable
            width=2,
            dont_extend_width=True,
        )

        search_input = Window(
            content=BufferControl(
                buffer=self.search_buffer,
                key_bindings=self._kb,
            ),
            height=COMMAND_PALETTE_SEARCH_INPUT_HEIGHT,
            dont_extend_height=True,
        )

        search_row = VSplit([search_prompt, search_input])

        separator = Window(height=COMMAND_PALLETE_SEPARATOR_HEIGHT, style="class:palette.separator")

        # Command list
        command_list = Window(
            content=FormattedTextControl(text=self._get_command_list_text),
            height=self._height,
            dont_extend_height=True,
        )

        # Combine with padding and background style
        body = HSplit([title, separator, search_row, separator, command_list])
        return Box(
            body,
            padding_left=COMMAND_PALETTE_BOX_PADDING_LEFT,
            padding_right=COMMAND_PALETTE_BOX_PADDING_RIGHT,
            padding_top=COMMAND_PALETTE_BOX_PADDING_TOP,
            padding_bottom=COMMAND_PALETTE_BOX_PADDING_BOTTOM,
            style="class:palette.box",
        )

    def __pt_container__(self) -> Box:
        """Return the container for prompt_toolkit."""
        return self._container

    @property
    def key_bindings(self) -> KeyBindings:
        """Return key bindings for external access."""
        return self._kb
