"""Dialog components: a choice, a message, and a text input, each in a Panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import WindowAlign

from koda_tui.appearance import Tokens, Width, compose
from koda_tui.ui.components.panel import Panel
from koda_tui.ui.primitives import Input, Spacer, Text

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.key_binding import KeyPressEvent

BUTTON_STYLE = Tokens.Text.MUTED
SELECTED_BUTTON_STYLE = compose(Tokens.Surface.SELECTED, Tokens.Text.STRONG)


@dataclass(frozen=True, slots=True)
class DialogChoice:
    label: str
    on_select: Callable[[], None]
    key: str | None = None  # Selects this choice directly, e.g. "y".


class ChoiceDialog:
    """Dialog for selecting one of a small number of choices."""

    def __init__(
        self,
        message: str,
        choices: list[DialogChoice],
        on_cancel: Callable[[], None],
    ) -> None:
        self._choices = choices
        self._selected = 0
        self._panel = Panel(
            message,
            [Text(self._choice_text, align=WindowAlign.CENTER, focusable=True)],
            on_close=on_cancel,
            key_bindings=self._create_keybindings(),
            width=Width.MEDIUM,
        )

    def __pt_container__(self) -> Panel:
        return self._panel

    def _on_enter(self, _event: KeyPressEvent) -> None:
        self._choices[self._selected].on_select()

    def _on_previous(self, _event: KeyPressEvent) -> None:
        self._selected = (self._selected - 1) % len(self._choices)

    def _on_next(self, _event: KeyPressEvent) -> None:
        self._selected = (self._selected + 1) % len(self._choices)

    def _create_keybindings(self) -> KeyBindings:
        kb = KeyBindings()
        kb.add(Keys.Enter)(self._on_enter)
        kb.add(Keys.Left)(self._on_previous)
        kb.add(Keys.Right)(self._on_next)
        kb.add(Keys.Up)(self._on_previous)
        kb.add(Keys.Down)(self._on_next)
        kb.add("tab")(self._on_next)
        for choice in self._choices:
            if choice.key is not None:
                kb.add(choice.key)(lambda _event, choice=choice: choice.on_select())
        return kb

    def _choice_text(self) -> FormattedText:
        result: list[tuple[str, str]] = []
        for index, choice in enumerate(self._choices):
            if index:
                result.append(("", "  "))
            style = SELECTED_BUTTON_STYLE if index == self._selected else BUTTON_STYLE
            result.append((style, f" {choice.label} "))
        return FormattedText(result)


class MessageDialog:
    """Dialog for showing a non-input message; Enter or Escape closes it."""

    def __init__(self, title: str, detail: str, on_close: Callable[[], None]) -> None:
        kb = KeyBindings()
        kb.add(Keys.Enter)(lambda _event: on_close())
        self._panel = Panel(
            title,
            [Text(detail, style=Tokens.Text.MUTED, wrap=True, focusable=True)],
            on_close=on_close,
            key_bindings=kb,
            width=Width.MEDIUM,
        )

    def __pt_container__(self) -> Panel:
        return self._panel


class InputDialog:
    """Dialog for single-line text input with optional masking."""

    def __init__(
        self,
        title: str,
        on_submit: Callable[[str], None],
        on_cancel: Callable[[], None],
        *,
        detail: str | None = None,
        mask_input: bool = False,
    ) -> None:
        self._on_submit = on_submit
        self.input_buffer = Buffer()

        kb = KeyBindings()
        kb.add(Keys.Enter)(self._on_enter)
        detail_rows = [Text(detail, style=Tokens.Text.MUTED, wrap=True), Spacer()] if detail else []
        self._panel = Panel(
            title,
            [*detail_rows, Input(self.input_buffer, masked=mask_input)],
            on_close=on_cancel,
            key_bindings=kb,
            width=Width.SMALL,
        )

    def __pt_container__(self) -> Panel:
        return self._panel

    def _on_enter(self, _event: KeyPressEvent) -> None:
        text = self.input_buffer.text.strip()
        if text:
            self._on_submit(text)
