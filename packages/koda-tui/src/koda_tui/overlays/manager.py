"""Modal overlay stack manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.layout import Float

if TYPE_CHECKING:
    from prompt_toolkit import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.layout import FloatContainer
    from prompt_toolkit.layout.containers import AnyContainer

    from koda_tui.overlays.base import Overlay

    FocusTarget = Buffer | AnyContainer


class OverlayManager:
    """Manage modal overlay content in an app-level ``FloatContainer``.

    The root layout owns the ``FloatContainer`` passed to this manager.
    Individual overlays are wrapped in prompt_toolkit ``Float`` objects and
    mounted into that root container. Only the top overlay is visible; older
    stack entries are kept so they can be restored when the top overlay closes.
    """

    def __init__(
        self,
        root_container: FloatContainer,
        app: Application[None],
        *,
        fallback_focus_target: FocusTarget | None = None,
    ) -> None:
        """Create a manager for modal overlays.

        ``root_container`` is the app-level float host. ``fallback_focus_target``
        is focused whenever the overlay stack becomes empty, normally the main
        input buffer.
        """
        self._root = root_container
        self._app = app
        self._fallback_focus_target = fallback_focus_target
        self._stack: list[tuple[Overlay, Float]] = []

    @property
    def is_open(self) -> bool:
        """Return whether the overlay stack currently contains any overlays."""
        return len(self._stack) > 0

    def _focus(self, overlay: Overlay) -> None:
        """Focus the active overlay's declared focus target."""
        self._app.layout.focus(overlay.focus_target)

    def _focus_fallback(self) -> None:
        """Restore focus after the last overlay has been removed."""
        if self._fallback_focus_target is not None:
            self._app.layout.focus(self._fallback_focus_target)

    def push(self, overlay: Overlay, *, width: int | None = None) -> None:
        """Show ``overlay`` as the new top modal overlay.

        Existing overlay floats are temporarily removed from the root
        container, but their stack entries are retained so ``pop`` can reveal
        the previous overlay.
        """
        self._root.floats.clear()

        float_item = Float(content=overlay, width=width)
        self._root.floats.append(float_item)
        self._stack.append((overlay, float_item))
        self._focus(overlay)

    def pop(self) -> Overlay | None:
        """Close and return the top overlay.

        If another overlay remains on the stack, it is restored and focused.
        Otherwise, focus returns to the fallback target.
        """
        if not self._stack:
            return None

        overlay, _ = self._stack.pop()
        self._root.floats.clear()

        if self._stack:
            prev_overlay, prev_float = self._stack[-1]
            self._root.floats.append(prev_float)
            self._focus(prev_overlay)
        else:
            self._focus_fallback()

        return overlay

    def clear(self) -> None:
        """Close every overlay and restore fallback focus."""
        self._stack.clear()
        self._root.floats.clear()
        self._focus_fallback()
