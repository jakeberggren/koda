"""Single-select searchable palette overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Dimension, VSplit

from koda_tui.appearance import Tokens, Width, compose
from koda_tui.ui.components import Panel
from koda_tui.ui.primitives import Input, List, ListState, Spacer, Text

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.key_binding import KeyPressEvent
    from prompt_toolkit.layout import AnyContainer

    from koda_tui.ui.primitives import ListItem


_PROMPT_STYLE = compose(Tokens.Text.ACCENT, Tokens.Text.STRONG)


class PaletteOverlay:
    """Single-select searchable palette overlay.

    Composes search input, scrollable list, and optional footer into a
    floating Frame. Enter selects the current item; Escape closes.
    """

    def __init__(  # noqa: PLR0913 - palette construction wires several UI callbacks/options
        self,
        items: list[ListItem],
        on_select: Callable[[ListItem], None],
        on_close: Callable[[], None],
        invalidate: Callable[[], None],
        *,
        title: str = "Commands",
        footer: StyleAndTextTuples | None = None,
        list_heading: str | None = None,
        shortcuts: dict[str, Callable[[ListItem | None], None]] | None = None,
    ) -> None:
        self._title = title
        self._on_select = on_select
        self._on_close = on_close
        self._invalidate = invalidate
        self._shortcuts = shortcuts or {}
        self._state = ListState(items)
        self._list = List(
            self._state, heading=list_heading, height=Dimension(min=5, max=20, preferred=20)
        )
        self.search_buffer = Buffer(on_text_changed=self._on_search_changed)
        self._kb = self._create_keybindings()
        self._container = self._build_container(footer)

    def _on_search_changed(self, _buffer: Buffer) -> None:
        """Filter items when search text changes."""
        self._state.set_search(self.search_buffer.text)
        self._invalidate()

    @property
    def _selected_item(self) -> ListItem | None:
        return self._state.selected_item

    def _move_selection(self, delta: int, *, wrap: bool = True) -> None:
        """Move selection and trigger re-render."""
        self._state.move_selection(delta, wrap=wrap)
        self._invalidate()

    def _execute_selected(self) -> None:
        """Execute the currently selected item's handler."""
        item = self._selected_item
        if item is not None:
            self._on_select(item)

    def _on_enter(self, _event: KeyPressEvent) -> None:
        self._execute_selected()

    def _on_up(self, _event: KeyPressEvent) -> None:
        self._move_selection(-1)

    def _on_down(self, _event: KeyPressEvent) -> None:
        self._move_selection(1)

    def _make_shortcut_handler(
        self, handler: Callable[[ListItem | None], None]
    ) -> Callable[[KeyPressEvent], None]:
        """Create a handler that calls the shortcut with the current item."""

        def _shortcut(_event: KeyPressEvent) -> None:
            handler(self._selected_item)

        return _shortcut

    def _create_keybindings(self) -> KeyBindings:
        """Create key bindings for palette navigation."""
        kb = KeyBindings()
        kb.add(Keys.Enter, eager=True)(self._on_enter)
        kb.add(Keys.Up, eager=True)(self._on_up)
        kb.add(Keys.Down, eager=True)(self._on_down)

        for key, handler in self._shortcuts.items():
            kb.add(key)(self._make_shortcut_handler(handler))

        return kb

    def _build_container(self, footer: StyleAndTextTuples | None) -> Panel:
        """Build the palette UI container."""
        search_row = VSplit(
            [
                Text("\u276f ", style=_PROMPT_STYLE, fit=True),
                Input(self.search_buffer),
            ]
        )
        body: list[AnyContainer] = [search_row, Spacer(), self._list]
        if footer:
            body += [Spacer(), Text(footer, wrap=True)]
        return Panel(
            self._title,
            body,
            on_close=self._on_close,
            key_bindings=self._kb,
            width=Width.LARGE,
        )

    def __pt_container__(self) -> AnyContainer:
        return self._container
