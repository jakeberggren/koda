"""Picker widget: a searchable list in a panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, VSplit, Window

from koda_tui.appearance import Height, Spacing, Width
from koda_tui.ui.primitives import Input, List, ListState, Overflow, Spacer, Text
from koda_tui.ui.widgets.panel import Panel
from koda_tui.ui.widgets.prompt import Prompt

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.key_binding import KeyPressEvent
    from prompt_toolkit.layout import AnyContainer

    from koda_tui.ui.primitives import ListItem

    type Shortcut[T] = Callable[[ListItem[T] | None], None]

LIST_HEIGHT = Dimension(min=Height.SMALL, max=Height.LARGE, preferred=Height.LARGE)


class Picker[T]:
    """A search field over a list, in a panel. Typing filters the items, up and down
    move the selection, enter picks it and escape closes.

    ``shortcuts`` bind more keys to actions on the selected item. ``label_width``
    cuts longer labels, so the details stay in one column.
    """

    def __init__(  # noqa: PLR0913 - each option is a distinct part of the picker
        self,
        title: str,
        items: list[ListItem[T]],
        *,
        on_select: Callable[[ListItem[T]], None],
        on_close: Callable[[], None],
        heading: str | None = None,
        footer: StyleAndTextTuples | None = None,
        shortcuts: dict[str, Shortcut[T]] | None = None,
        label_width: int | None = None,
    ) -> None:
        self.state = ListState(items)
        self.search = Buffer(on_text_changed=lambda buffer: self.state.set_search(buffer.text))
        body: list[AnyContainer] = [
            VSplit([Prompt(), Window(width=Spacing.GAP), Input(self.search)]),
            Spacer(),
            List(self.state, heading=heading, height=LIST_HEIGHT, label_width=label_width),
        ]
        if footer:
            body += [Spacer(), Text(footer, overflow=Overflow.WRAP)]
        self._panel = Panel(
            title,
            body,
            on_close=on_close,
            key_bindings=_key_bindings(self.state, on_select, shortcuts or {}),
            width=Width.LARGE,
        )

    def __pt_container__(self) -> Panel:
        return self._panel


def _key_bindings[T](
    state: ListState[T],
    on_select: Callable[[ListItem[T]], None],
    shortcuts: dict[str, Shortcut[T]],
) -> KeyBindings:
    kb = KeyBindings()

    @kb.add(Keys.Up, eager=True)
    def _up(_event: KeyPressEvent) -> None:
        state.move_selection(-1, wrap=True)

    @kb.add(Keys.Down, eager=True)
    def _down(_event: KeyPressEvent) -> None:
        state.move_selection(1, wrap=True)

    @kb.add(Keys.Enter, eager=True)
    def _enter(_event: KeyPressEvent) -> None:
        if (item := state.selected_item) is not None:
            on_select(item)

    _add_shortcuts(kb, state, shortcuts)
    return kb


def _add_shortcuts[T](
    kb: KeyBindings,
    state: ListState[T],
    shortcuts: dict[str, Shortcut[T]],
) -> None:
    for key, shortcut in shortcuts.items():
        kb.add(key)(lambda _event, shortcut=shortcut: shortcut(state.selected_item))
