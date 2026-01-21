"""Palette manager for stacked command palettes and dialogs."""

from typing import TYPE_CHECKING, Any

from prompt_toolkit.layout import Float

from koda_tui.app.layout import TUILayout

if TYPE_CHECKING:
    from prompt_toolkit import Application


class PaletteManager:
    """Manages a stack of floating overlays (palettes, dialogs)."""

    def __init__(self, layout: TUILayout) -> None:
        self._app: Application[Any] | None = None
        self._layout = layout
        # Internal stack of (content, float) tuples
        self._stack: list[tuple[Any, Float]] = []

    def set_app(self, app: "Application[Any]") -> None:
        """Set the application reference for focus management."""
        self._app = app

    @property
    def _floats(self) -> list[Float]:
        """Access the layout's floats list."""
        return self._layout.root_container.floats

    @property
    def is_open(self) -> bool:
        """Check if any overlay is open."""
        return len(self._stack) > 0

    def _focus_content(self, content: Any) -> None:
        """Focus the appropriate buffer on the content."""
        if not self._app:
            return
        if hasattr(content, "search_buffer"):
            self._app.layout.focus(content.search_buffer)
        elif hasattr(content, "input_buffer"):
            self._app.layout.focus(content.input_buffer)

    def push(self, content: Any, width: int | None = None) -> None:
        """Push a new overlay onto the stack.

        The new overlay replaces the current one visually (only one shown at a time).
        """
        # Remove current float from display (but keep in stack)
        if self._floats:
            self._floats.clear()

        # Create and show new float
        float_item = Float(content=content, width=width)
        self._floats.append(float_item)
        self._stack.append((content, float_item))

        self._focus_content(content)

    def pop(self) -> bool:
        """Pop the top overlay from the stack."""
        if not self._stack:
            return False

        # Remove current
        self._stack.pop()
        self._floats.clear()

        if self._stack:
            # Show previous overlay
            prev_content, prev_float = self._stack[-1]
            self._floats.append(prev_float)
            self._focus_content(prev_content)
            return True

        # Stack empty, focus back to main input
        if self._app:
            self._app.layout.focus(self._layout.input_area.buffer)
        return False

    def clear(self) -> None:
        """Close all overlays."""
        self._stack.clear()
        self._floats.clear()

        if self._app:
            self._app.layout.focus(self._layout.input_area.buffer)
