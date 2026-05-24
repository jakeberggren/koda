"""Yes/No confirmation dialog overlay."""

from __future__ import annotations

import shutil
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
    from prompt_toolkit.layout import AnyContainer


def _calculate_dialog_width() -> int:
    """Return confirmation dialog width based on the current terminal size."""
    term_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    return max(40, min(60, term_width // 2))


class ConfirmDialog:
    """Dialog for yes/no confirmation."""

    def __init__(
        self,
        message: str,
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None],
        *,
        width: int | None = None,
    ) -> None:
        self._message = message
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._selected = True  # True = Yes, False = No
        self.preferred_width = width if width is not None else _calculate_dialog_width()

        self.input_buffer = Buffer()
        self._kb = self._create_keybindings()
        self._container = self._build_container()

    def __pt_container__(self) -> AnyContainer:
        return self._container

    @property
    def focus_target(self) -> Buffer:
        """Return the prompt_toolkit target to focus when opened."""
        return self.input_buffer

    def _create_keybindings(self) -> KeyBindings:
        kb = KeyBindings()
        kb.add(Keys.Escape, eager=True)(self._on_escape)
        kb.add(Keys.Enter)(self._on_enter)
        kb.add(Keys.Left)(self._on_toggle)
        kb.add(Keys.Right)(self._on_toggle)
        kb.add("tab")(self._on_toggle)
        kb.add("y")(self._on_yes)
        kb.add("n")(self._on_no)
        return kb

    def _on_escape(self, _event: KeyPressEvent) -> None:
        self._on_cancel()

    def _on_enter(self, _event: KeyPressEvent) -> None:
        if self._selected:
            self._on_confirm()
        else:
            self._on_cancel()

    def _on_toggle(self, _event: KeyPressEvent) -> None:
        self._selected = not self._selected

    def _on_yes(self, _event: KeyPressEvent) -> None:
        self._on_confirm()

    def _on_no(self, _event: KeyPressEvent) -> None:
        self._on_cancel()

    def _button_text(self) -> list[tuple[str, str]]:
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
            content=FormattedTextControl(text=self._button_text),
            height=1,
            dont_extend_height=True,
            align=WindowAlign.CENTER,
            style="class:dialog.box",
        )

        # Hidden buffer for focus (keybindings need a focused BufferControl)
        focus_buffer = Window(
            content=BufferControl(
                buffer=self.input_buffer,
                key_bindings=self._kb,
            ),
            height=0,
            dont_extend_height=True,
        )

        body = HSplit([title_row, separator, buttons, focus_buffer])
        box = Box(
            body,
            padding_left=2,
            padding_right=2,
            padding_top=1,
            padding_bottom=1,
            style="class:dialog.box",
        )
        return Frame(body=box, style="class:dialog.frame")
