from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    BufferControl,
    FormattedTextControl,
    HSplit,
    UIContent,
    UIControl,
    VSplit,
    Window,
    WindowAlign,
)
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.widgets import Box, Frame

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.key_binding import KeyPressEvent

    from koda_tui.ui.palette.commands import Command


class PaletteListControl(UIControl):
    """Scrollable command list control used inside the command palette."""

    def __init__(self, palette: CommandPalette) -> None:
        self._palette = palette
        self._scroll_offset = 0
        self._view_height = 0

    def reset_scroll(self) -> None:
        """Reset the list scroll position to the top."""
        self._scroll_offset = 0

    def _ensure_scroll_bounds(self, row_count: int) -> None:
        """Clamp the scroll offset to the available logical rows."""
        max_offset = max(0, row_count - max(1, self._view_height))
        self._scroll_offset = max(0, min(self._scroll_offset, max_offset))

    def _group_header_index(self, rows: list[_PaletteRow], row_index: int) -> int | None:
        """Return the nearest group header above the given row, if any."""
        for index in range(row_index - 1, -1, -1):
            if rows[index].kind == "group":
                return index
        return None

    def _scroll_target_for_upward_move(
        self, rows: list[_PaletteRow], selected_row: int, viewport_height: int
    ) -> int:
        """Return the offset to use when the selection moves above the viewport."""
        group_header_index = self._group_header_index(rows, selected_row)
        if group_header_index is not None and selected_row - group_header_index < viewport_height:
            return group_header_index
        return selected_row

    def _content_state(
        self, *, height: int | None = None
    ) -> tuple[list[_PaletteRow], int | None, int]:
        """Return rows, selected row, and active viewport height."""
        rows, selected_row = self._palette.build_command_rows()
        viewport_height = max(1, height if height is not None else self._view_height)
        self._view_height = viewport_height
        return rows, selected_row, viewport_height

    def _group_header_offset(
        self, rows: list[_PaletteRow], selected_row: int, viewport_height: int
    ) -> int | None:
        """Return the group header offset when that header should be revealed."""
        group_header_index = self._group_header_index(rows, selected_row)
        if (
            group_header_index is not None
            and group_header_index < self._scroll_offset
            and selected_row - group_header_index < viewport_height
        ):
            return group_header_index
        return None

    def _selection_scroll_offset(
        self, rows: list[_PaletteRow], selected_row: int, viewport_height: int
    ) -> int | None:
        """Return the desired scroll offset for the current selection, if it should change."""
        if selected_row < self._scroll_offset:
            return self._scroll_target_for_upward_move(rows, selected_row, viewport_height)
        if selected_row >= self._scroll_offset + viewport_height:
            return selected_row - viewport_height + 1
        return self._group_header_offset(rows, selected_row, viewport_height)

    def ensure_selection_visible(self, *, height: int | None = None) -> None:
        """Adjust scroll offset so the selected command stays visible."""
        if height is None and self._view_height <= 0:
            return

        rows, selected_row, viewport_height = self._content_state(height=height)
        self._ensure_scroll_bounds(len(rows))

        if selected_row is None:
            self._scroll_offset = 0
            return

        scroll_offset = self._selection_scroll_offset(rows, selected_row, viewport_height)
        if scroll_offset is not None:
            self._scroll_offset = scroll_offset

        self._ensure_scroll_bounds(len(rows))

    def mouse_handler(self, mouse_event: MouseEvent) -> None:
        """Handle mouse wheel scrolling in the palette list."""
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self._palette.move_selection_clamped(-1)
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self._palette.move_selection_clamped(1)

    def create_content(self, width: int, height: int) -> UIContent:  # noqa: ARG002
        """Create viewport content for the command list."""
        rows, selected_row, viewport_height = self._content_state(height=height)
        self.ensure_selection_visible(height=height)

        visible_rows = [
            row.text for row in rows[self._scroll_offset : self._scroll_offset + viewport_height]
        ]

        cursor_y = 0
        if selected_row is not None:
            cursor_y = max(0, min(viewport_height - 1, selected_row - self._scroll_offset))

        def get_line(i: int) -> FormattedText:
            if 0 <= i < len(visible_rows):
                return visible_rows[i]
            return FormattedText([])

        return UIContent(
            get_line=get_line,
            line_count=len(visible_rows),
            cursor_position=Point(x=0, y=cursor_y),
        )


@dataclass(frozen=True, slots=True)
class _PaletteRow:
    """Logical command palette row with lightweight render metadata."""

    kind: str
    text: FormattedText
    command: Command | None = None


@dataclass(frozen=True, slots=True)
class PaletteOptions:
    """Optional presentation and interaction settings for a command palette."""

    height: int = 10
    footer: StyleAndTextTuples | None = None
    shortcuts: dict[str, Callable[[Command | None], None]] | None = None


class CommandPalette:
    """Floating command palette with fuzzy search."""

    def __init__(
        self,
        commands: list[Command],
        on_close: Callable[[], None],
        invalidate: Callable[[], None],
        options: PaletteOptions,
    ) -> None:
        self.commands = commands
        self.on_close = on_close
        self.selected_index = 0
        self._filtered_commands: list[Command] = list(commands)
        self._rows: list[_PaletteRow] = []
        self._invalidate = invalidate
        self._height = options.height
        self._footer = options.footer
        self._shortcuts = options.shortcuts or {}

        # Search buffer
        self.search_buffer = Buffer(
            on_text_changed=self._on_search_changed,
        )

        self._list_control = PaletteListControl(self)

        # Key bindings local to the palette
        self._kb = self._create_keybindings()

        # Build the container
        self._container = self._build_container()
        self._rebuild_rows()

    def _rebuild_rows(self) -> None:
        """Rebuild the canonical display rows and clamp selection to command rows."""
        self._rows = self._build_rows()
        self._clamp_selection()

    def _command_row_indexes(self) -> list[int]:
        """Return display row indexes that correspond to executable commands."""
        return [index for index, row in enumerate(self._rows) if row.command is not None]

    def _clamp_selection(self) -> None:
        """Clamp selection to the available command rows."""
        command_row_indexes = self._command_row_indexes()
        if not command_row_indexes:
            self.selected_index = 0
            return
        self.selected_index = max(0, min(self.selected_index, len(command_row_indexes) - 1))

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
        self._rebuild_rows()
        self._list_control.reset_scroll()
        self._invalidate()

    def move_selection_wrapped(self, delta: int) -> None:
        """Move selection by delta, wrapping around and keep it visible."""
        command_row_indexes = self._command_row_indexes()
        if not command_row_indexes:
            return
        self.selected_index = (self.selected_index + delta) % len(command_row_indexes)
        self._rebuild_rows()
        self._list_control.ensure_selection_visible()
        self._invalidate()

    def move_selection_clamped(self, delta: int) -> None:
        """Move selection by delta without wrapping past the list boundaries."""
        command_row_indexes = self._command_row_indexes()
        if not command_row_indexes:
            return
        next_index = self.selected_index + delta
        self.selected_index = max(0, min(next_index, len(command_row_indexes) - 1))
        self._rebuild_rows()
        self._list_control.ensure_selection_visible()
        self._invalidate()

    def _execute_selected(self) -> None:
        """Execute the currently selected command.

        Note: Does not auto-close. Handlers manage stack via palette_manager.
        """
        cmd = self.selected_command
        if cmd is not None:
            cmd.handler()

    @property
    def selected_command(self) -> Command | None:
        """Return the currently selected command, or None if list is empty."""
        command_row_indexes = self._command_row_indexes()
        if not command_row_indexes:
            return None
        selected_row_index = command_row_indexes[self.selected_index]
        return self._rows[selected_row_index].command

    def _create_keybindings(self) -> KeyBindings:  # noqa: C901 - allow complex
        """Create key bindings for palette navigation."""
        kb = KeyBindings()

        @kb.add(Keys.Escape, eager=True)
        def _close(_event: KeyPressEvent) -> None:
            self.on_close()

        @kb.add(Keys.Enter, eager=True)
        def _select(_event: KeyPressEvent) -> None:
            self._execute_selected()

        @kb.add(Keys.Up, eager=True)
        def _move_up(_event: KeyPressEvent) -> None:
            self.move_selection_wrapped(-1)

        @kb.add(Keys.Down, eager=True)
        def _move_down(_event: KeyPressEvent) -> None:
            self.move_selection_wrapped(1)

        for key, handler in self._shortcuts.items():

            @kb.add(key)
            def _shortcut(
                _event: KeyPressEvent, _handler: Callable[[Command | None], None] = handler
            ) -> None:
                _handler(self.selected_command)

        return kb

    def _group_commands(self) -> list[tuple[str | None, list[Command]]]:
        """Group filtered commands by their group label."""
        grouped: list[tuple[str | None, list[Command]]] = []
        group_map: dict[str, list[Command]] = {}
        ungrouped: list[Command] = []

        for cmd in self._filtered_commands:
            if not cmd.group:
                ungrouped.append(cmd)
                continue

            group_commands = group_map.get(cmd.group)
            if group_commands is None:
                group_commands = []
                group_map[cmd.group] = group_commands
                grouped.append((cmd.group, group_map[cmd.group]))
            group_commands.append(cmd)

        if ungrouped:
            return [(None, ungrouped), *grouped]
        return grouped

    def _get_max_label_width(self) -> int:
        """Calculate max label width for alignment."""
        return max((len(cmd.label) for cmd in self._filtered_commands), default=0)

    def _build_command_row(
        self, cmd: Command, *, is_selected: bool, max_label_width: int
    ) -> _PaletteRow:
        """Build a formatted row for a single command."""
        style = "class:palette.selected" if is_selected else "class:palette.item"
        dim_style = "class:palette.selected" if is_selected else "class:palette.dim"
        prefix = "- " if is_selected else "  "
        padded_label = cmd.label.ljust(max_label_width)
        line: StyleAndTextTuples = [(style, f"{prefix}{padded_label}")]
        if cmd.description:
            line.append((dim_style, f"  {cmd.description}"))
        return _PaletteRow(kind="item", text=FormattedText(line), command=cmd)

    @staticmethod
    def _empty_row() -> _PaletteRow:
        return _PaletteRow(
            kind="empty",
            text=FormattedText([("class:palette.empty", "  No results found")]),
        )

    @staticmethod
    def _spacer_row() -> _PaletteRow:
        return _PaletteRow(kind="spacer", text=FormattedText([]))

    @staticmethod
    def _group_row(group: str) -> _PaletteRow:
        return _PaletteRow(
            kind="group",
            text=FormattedText([("class:palette.group", group)]),
        )

    def _append_group_header(self, rows: list[_PaletteRow], group: str | None) -> None:
        if not group:
            return
        if rows:
            rows.append(self._spacer_row())
        rows.append(self._group_row(group))

    def _append_command_rows(
        self,
        rows: list[_PaletteRow],
        commands: list[Command],
        *,
        max_label_width: int,
        command_index: int,
    ) -> int:
        for cmd in commands:
            rows.append(
                self._build_command_row(
                    cmd,
                    is_selected=command_index == self.selected_index,
                    max_label_width=max_label_width,
                )
            )
            command_index += 1
        return command_index

    def _build_rows(self) -> list[_PaletteRow]:
        """Build logical rows for the command list in final display order."""
        if not self._filtered_commands:
            return [self._empty_row()]

        rows: list[_PaletteRow] = []
        max_label_width = self._get_max_label_width()
        command_index = 0

        for group, commands in self._group_commands():
            self._append_group_header(rows, group)
            command_index = self._append_command_rows(
                rows,
                commands,
                max_label_width=max_label_width,
                command_index=command_index,
            )

        return rows or [self._spacer_row()]

    def build_command_rows(self) -> tuple[list[_PaletteRow], int | None]:
        """Return logical rows and the selected display row index."""
        command_row_indexes = self._command_row_indexes()
        selected_row = None
        if command_row_indexes:
            selected_row = command_row_indexes[self.selected_index]
        return self._rows, selected_row

    def _build_container(self) -> Frame:
        """Build the palette UI container."""
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

        command_list = Window(
            content=self._list_control,
            height=self._height,
            dont_extend_height=True,
        )

        children = [title_row, separator, search_row, separator, command_list]
        if self._footer:
            footer_row = Window(
                content=FormattedTextControl(text=self._footer),
                height=1,
                dont_extend_height=True,
                align=WindowAlign.LEFT,
            )
            children.extend([separator, footer_row])
        body = HSplit(children)
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
