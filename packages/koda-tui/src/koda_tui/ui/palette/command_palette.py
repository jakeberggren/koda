from __future__ import annotations

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
from prompt_toolkit.widgets import Box, Frame

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.key_binding import KeyPressEvent

    from koda_tui.ui.palette.commands import Command


class CommandPalette:
    """Floating command palette with fuzzy search."""

    def __init__(
        self,
        commands: list[Command],
        on_close: Callable[[], None],
        height: int = 10,
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
        """Execute the currently selected command.

        Note: Does not auto-close. Handlers manage stack via palette_manager.
        """
        if self._filtered_commands:
            cmd = self._filtered_commands[self.selected_index]
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

    def _group_commands(self) -> list[tuple[str | None, list[Command]]]:
        """Group filtered commands by their group label."""
        grouped: list[tuple[str | None, list[Command]]] = []
        group_map: dict[str, list[Command]] = {}
        ungrouped: list[Command] = []

        for cmd in self._filtered_commands:
            if cmd.group:
                if cmd.group not in group_map:
                    group_map[cmd.group] = []
                    grouped.append((cmd.group, group_map[cmd.group]))
                group_map[cmd.group].append(cmd)
            else:
                ungrouped.append(cmd)

        if ungrouped:
            return [(None, ungrouped), *grouped]
        return grouped

    def _get_empty_command_list_text(self) -> list[tuple[str, str]]:
        """Return placeholder text when no commands match."""
        return [("class:palette.empty", "  No matching commands\n")]

    def _get_max_label_width(self) -> int:
        """Calculate max label width for alignment."""
        return max((len(cmd.label) for cmd in self._filtered_commands), default=0)

    def _append_group_header(self, result: list[tuple[str, str]], group: str | None) -> None:
        """Append a group header to the formatted result."""
        if not group:
            return
        if result:
            result.append(("class:palette.dim", "\n"))
        result.append(("class:palette.group", f"{group}\n"))

    def _append_command_line(
        self,
        result: list[tuple[str, str]],
        cmd: Command,
        *,
        max_label_width: int,
        is_selected: bool,
    ) -> None:
        """Append a formatted command line to the result."""
        style = "class:palette.selected" if is_selected else "class:palette.item"
        dim_style = "class:palette.selected" if is_selected else "class:palette.dim"
        prefix = "- " if is_selected else "  "
        padded_label = cmd.label.ljust(max_label_width)
        result.append((style, f"{prefix}{padded_label}"))
        if cmd.description:
            result.append((dim_style, f"  {cmd.description}"))
        result.append((style, "\n"))

    def _get_command_list_text(self) -> list[tuple[str, str]]:
        """Generate formatted text for the command list."""
        if not self._filtered_commands:
            return self._get_empty_command_list_text()

        result: list[tuple[str, str]] = []
        max_label_width = self._get_max_label_width()
        command_index = 0

        for group, commands in self._group_commands():
            self._append_group_header(result, group)
            for cmd in commands:
                is_selected = command_index == self.selected_index
                self._append_command_line(
                    result,
                    cmd,
                    max_label_width=max_label_width,
                    is_selected=is_selected,
                )
                command_index += 1

        return result

    def _build_container(self) -> Frame:
        """Build the palette UI container."""
        # Title
        title_text = Window(
            content=FormattedTextControl(text=[("class:palette.title", "Commands")]),
            height=1,
            align=WindowAlign.LEFT,
            dont_extend_height=True,
        )

        esc_hint = Window(
            content=FormattedTextControl(text=[("class:palette.hint", "esc")]),
            height=1,
            width=3,
            dont_extend_height=True,
            dont_extend_width=True,
            align=WindowAlign.RIGHT,
        )

        title_row = VSplit([title_text, esc_hint])

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
            height=1,
            dont_extend_height=True,
        )

        search_row = VSplit([search_prompt, search_input])

        separator = Window(height=1, style="class:palette.separator")

        # Command list
        command_list = Window(
            content=FormattedTextControl(text=self._get_command_list_text),
            height=self._height,
            dont_extend_height=True,
        )

        # Combine with padding and background style
        body = HSplit([title_row, separator, search_row, separator, command_list])
        box = Box(
            body,
            padding_left=2,
            padding_right=2,
            padding_top=1,
            padding_bottom=1,
            style="class:palette.box",
        )
        return Frame(body=box, style="class:palette.frame")

    def __pt_container__(self) -> Frame:
        """Return the container for prompt_toolkit."""
        return self._container

    @property
    def key_bindings(self) -> KeyBindings:
        """Return key bindings for external access."""
        return self._kb
