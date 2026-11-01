"""Overlays: containers shown one at a time above the screen, such as pickers and dialogs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout import Float

if TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.layout import FloatContainer
    from prompt_toolkit.layout.containers import AnyContainer

    type FocusTarget = Buffer | AnyContainer


class Overlays:
    """A stack of overlays floating in ``root``. Only the top one shows and has focus;
    closing it reveals the one below, and closing the last focuses ``fallback``.
    """

    def __init__(self, root: FloatContainer, *, fallback: FocusTarget | None = None) -> None:
        self._root = root
        self._fallback = fallback
        self._stack: list[Float] = []

    @property
    def is_open(self) -> bool:
        return bool(self._stack)

    def open(self, overlay: AnyContainer) -> None:
        """Show ``overlay`` above the others, and focus it."""
        self._stack.append(Float(content=overlay))
        self._show_top()

    def close(self) -> None:
        """Close the top overlay."""
        if self._stack:
            self._stack.pop()
            self._show_top()

    def close_all(self) -> None:
        self._stack.clear()
        self._show_top()

    def _show_top(self) -> None:
        """Float only the top overlay and focus it, or the fallback when none are left."""
        self._root.floats.clear()
        app = get_app()
        if self._stack:
            self._root.floats.append(self._stack[-1])
            # prompt_toolkit maps parents only on render. keys before it miss the overlay bindings.
            app.layout.update_parents_relations()
            app.layout.focus(self._stack[-1].content)
        elif self._fallback is not None:
            app.layout.focus(self._fallback)
        app.invalidate()
