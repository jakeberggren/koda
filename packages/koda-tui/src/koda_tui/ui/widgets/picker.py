"""Picker widget: a searchable list in a panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, VSplit

from koda_tui.appearance import Height, Icons, Spacing, Tokens, Width
from koda_tui.ui.primitives import Input, Overflow, Spacer, Text
from koda_tui.ui.widgets.list import List, ListState
from koda_tui.ui.widgets.panel import Panel
from koda_tui.ui.widgets.prompt import Prompt

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.key_binding import KeyPressEvent
    from prompt_toolkit.layout import AnyContainer

    from koda_tui.ui.widgets.list import ListItem

LIST_HEIGHT = Dimension(min=Height.SMALL, max=Height.LARGE, preferred=Height.LARGE)
HINT_DIVIDER = f" {Icons.DIVIDER} "


@dataclass(frozen=True, slots=True)
class Shortcut[T]:
    """A key that acts on the selected item."""

    key: Keys
    label: str
    action: str
    run: Callable[[ListItem[T] | None], None]


class Picker[T]:
    """A search field over a list, in a panel. Typing filters the items, up and down
    move the selection, enter picks it and escape closes.
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
        shortcuts: Sequence[Shortcut[T]] = (),
        label_width: int | None = None,
    ) -> None:
        self.state = ListState(items)
        self.search = Buffer(on_text_changed=lambda buffer: self.state.set_search(buffer.text))
        body: list[AnyContainer] = [
            VSplit([Prompt(), Input(self.search)], padding=Spacing.GAP),
            Spacer(),
            List(self.state, heading=heading, height=LIST_HEIGHT, label_width=label_width),
        ]
        if footer:
            body += [Spacer(), Text(footer, overflow=Overflow.WRAP)]
        if shortcuts:
            body += [Spacer(), Text(_hints(shortcuts), overflow=Overflow.WRAP)]
        self._panel = Panel(
            title,
            body,
            on_close=on_close,
            key_bindings=_key_bindings(self.state, on_select, shortcuts),
            width=Width.LARGE,
        )

    def __pt_container__(self) -> Panel:
        return self._panel


def _key_bindings[T](
    state: ListState[T],
    on_select: Callable[[ListItem[T]], None],
    shortcuts: Sequence[Shortcut[T]],
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
    shortcuts: Sequence[Shortcut[T]],
) -> None:
    for shortcut in shortcuts:
        kb.add(shortcut.key)(lambda _event, shortcut=shortcut: shortcut.run(state.selected_item))


def _hints[T](shortcuts: Sequence[Shortcut[T]]) -> StyleAndTextTuples:
    fragments: StyleAndTextTuples = []
    for index, shortcut in enumerate(shortcuts):
        if index:
            fragments.append((Tokens.Text.MUTED, HINT_DIVIDER))
        fragments += [
            (Tokens.Text.DEFAULT, shortcut.label),
            (Tokens.Text.MUTED, f" {shortcut.action}"),
        ]
    return fragments
