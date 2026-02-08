"""Yes/No confirmation dialog component."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
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


class ConfirmDialog:
    """Dialog for yes/no confirmation."""

    def __init__(
        self,
        message: str,
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self._message = message
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._selected = True  # True = Yes, False = No

        # Hidden buffer for focus (keybindings need a focused BufferControl)
        self.input_buffer = Buffer()
        self._kb = self._create_keybindings()
        self._container = self._build_container()

    def _create_keybindings(self) -> KeyBindings:  # noqa: C901 - allow complex
        kb = KeyBindings()

        @kb.add(Keys.Escape, eager=True)
        def _cancel(_event: KeyPressEvent) -> None:
            self._on_cancel()

        @kb.add(Keys.Enter)
        def _submit(_event: KeyPressEvent) -> None:
            if self._selected:
                self._on_confirm()
            else:
                self._on_cancel()

        @kb.add(Keys.Left)
        @kb.add(Keys.Right)
        @kb.add("tab")
        def _toggle(_event: KeyPressEvent) -> None:
            self._selected = not self._selected

        @kb.add("y")
        def _yes(_event: KeyPressEvent) -> None:
            self._on_confirm()

        @kb.add("n")
        def _no(_event: KeyPressEvent) -> None:
            self._on_cancel()

        return kb

    def _get_button_text(self) -> list[tuple[str, str]]:
        yes_style = "class:dialog.selected" if self._selected else "class:dialog.button"
        no_style = "class:dialog.button" if self._selected else "class:dialog.selected"
        return [
            (yes_style, " Yes "),
            ("class:dialog.box", " "),
            (no_style, " No "),
        ]

    def _build_container(self) -> Frame:
        title_text = Window(
            content=FormattedTextControl(
                text=[("class:dialog.title", self._message)],
            ),
            height=1,
            dont_extend_height=True,
            style="class:dialog.box",
        )

        esc_hint = Window(
            content=FormattedTextControl(text=[("class:dialog.hint", "esc")]),
            height=1,
            width=3,
            dont_extend_height=True,
            dont_extend_width=True,
            align=WindowAlign.RIGHT,
            style="class:dialog.box",
        )

        title_row = VSplit([title_text, esc_hint], style="class:dialog.box")

        separator = Window(height=1, style="class:dialog.box")

        buttons = Window(
            content=FormattedTextControl(text=self._get_button_text),
            height=1,
            dont_extend_height=True,
            align=WindowAlign.CENTER,
            style="class:dialog.box",
        )

        # Hidden focusable control to capture keybindings
        hidden_input = Window(
            content=BufferControl(buffer=self.input_buffer, key_bindings=self._kb),
            height=0,
        )

        body = HSplit([title_row, separator, buttons, hidden_input])

        box = Box(
            body,
            padding_left=2,
            padding_right=2,
            padding_top=1,
            padding_bottom=1,
            style="class:dialog.box",
        )
        return Frame(body=box, style="class:dialog.frame")

    def __pt_container__(self) -> Frame:
        return self._container

    @property
    def key_bindings(self) -> KeyBindings:
        return self._kb
