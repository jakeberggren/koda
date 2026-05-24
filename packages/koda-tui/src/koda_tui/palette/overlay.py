"""Single-select searchable palette overlay."""

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

from koda_tui.overlays.controls.footer import FooterControl
from koda_tui.overlays.controls.list import ListControl
from koda_tui.overlays.list.renderer import ListRenderer, RenderOptions
from koda_tui.overlays.list.state import ListState

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import StyleAndTextTuples
    from prompt_toolkit.key_binding import KeyPressEvent
    from prompt_toolkit.layout import AnyContainer

    from koda_tui.palette.items import ListItem


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
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        self._title = title
        self._on_select = on_select
        self._on_close = on_close
        self._invalidate = invalidate
        self._shortcuts = shortcuts or {}
        calculated_width, calculated_height = self._calculate_size()
        self.preferred_width = width if width is not None else calculated_width
        self._height = height if height is not None else calculated_height

        self._state = ListState(items=items)
        self._renderer = ListRenderer(
            RenderOptions(list_heading=list_heading) if list_heading else None
        )
        self.search_buffer = Buffer(on_text_changed=self._on_search_changed)
        self._list_control = ListControl(self._state, self._renderer)
        self._kb = self._create_keybindings()
        self._container = self._build_container(footer)

    @staticmethod
    def _calculate_size() -> tuple[int, int]:
        """Return palette width and list height based on terminal size."""
        size = shutil.get_terminal_size(fallback=(80, 24))
        width = max(60, min(80, size.columns // 2))
        height = max(5, min(20, size.lines // 2))
        return width, height

    @property
    def focus_target(self) -> Buffer:
        """Return the prompt_toolkit target to focus when opened."""
        return self.search_buffer

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

    def _on_escape(self, _event: KeyPressEvent) -> None:
        self._on_close()

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
        kb.add(Keys.Escape, eager=True)(self._on_escape)
        kb.add(Keys.Enter, eager=True)(self._on_enter)
        kb.add(Keys.Up, eager=True)(self._on_up)
        kb.add(Keys.Down, eager=True)(self._on_down)

        for key, handler in self._shortcuts.items():
            kb.add(key)(self._make_shortcut_handler(handler))

        return kb

    def _build_container(self, footer: StyleAndTextTuples | None) -> Frame:
        """Build the palette UI container."""
        title_text = Window(
            content=FormattedTextControl(text=[("class:palette.title", self._title)]),
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
        separator = Window(height=1, style="class:palette.separator")

        search_prompt = Window(
            content=FormattedTextControl(text=[("class:palette.prompt", "\u276f ")]),
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
        item_list = Window(
            content=self._list_control,
            height=self._height,
            dont_extend_height=True,
        )

        children = [title_row, separator, search_row, separator, item_list]

        if footer:
            footer_row = Window(
                content=FooterControl(footer),
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

    def __pt_container__(self) -> AnyContainer:
        return self._container
