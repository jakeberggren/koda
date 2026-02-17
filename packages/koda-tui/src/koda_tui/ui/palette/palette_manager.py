"""Palette manager for stacked command palettes and dialogs."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, Any

from prompt_toolkit.layout import Float

from koda_tui.ui.palette.api_key_dialog import ApiKeyDialog
from koda_tui.ui.palette.command_palette import CommandPalette
from koda_tui.ui.palette.commands.commands import get_commands
from koda_tui.ui.palette.confirm_dialog import ConfirmDialog

if TYPE_CHECKING:
    from collections.abc import Callable

    from prompt_toolkit import Application
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda_common.contracts import KodaBackend
    from koda_common.settings import SettingsManager
    from koda_tui.state import AppState
    from koda_tui.ui.layout import TUILayout
    from koda_tui.ui.palette.commands.command import Command


class PaletteManager:
    """Manages a stack of floating overlays (palettes, dialogs)."""

    def __init__(
        self,
        layout: TUILayout,
        state: AppState,
        settings: SettingsManager,
        invalidate: Callable[[], None],
        cancel_streaming: Callable[[], None],
    ) -> None:
        self._app: Application[Any] | None = None
        self._layout = layout
        self._state = state
        self._settings = settings
        self._invalidate = invalidate
        self._cancel_streaming = cancel_streaming
        self._stack: list[tuple[Any, Float]] = []

    def set_app(self, app: Application[Any]) -> None:
        """Set the application reference for focus management."""
        self._app = app

    @property
    def _floats(self) -> list[Float]:
        """Access the layout's floats list."""
        return self._layout.root_container.floats

    @property
    def _is_open(self) -> bool:
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

    def _push(self, content: Any, width: int | None = None) -> None:
        """Push a new overlay onto the stack.

        The new overlay replaces the current one visually (only one shown at a time).
        """
        if self._floats:
            self._floats.clear()

        float_item = Float(content=content, width=width)
        self._floats.append(float_item)
        self._stack.append((content, float_item))
        self._focus_content(content)

    def _get_default_commands(self, backend: KodaBackend) -> list[Command]:
        """Build the default root command list."""
        return get_commands(
            backend=backend,
            settings=self._settings,
            state=self._state,
            palette_manager=self,
            cancel_streaming=self._cancel_streaming,
        )

    @staticmethod
    def _get_terminal_size() -> tuple[int, int]:
        """Return terminal width and height using a safe fallback."""
        size = shutil.get_terminal_size(fallback=(80, 24))
        return size.columns, size.lines

    @staticmethod
    def _calculate_palette_size(term_width: int, term_height: int) -> tuple[int, int]:
        width = max(60, min(80, term_width // 2))
        height = max(5, min(20, term_height // 2))
        return width, height

    def toggle(self, backend: KodaBackend) -> None:
        """Toggle command palette visibility."""
        if self._is_open:
            self.close_all()
        else:
            commands = self._get_default_commands(backend)
            self.open_palette(commands)

    def open_palette(
        self,
        commands: list[Command],
        *,
        footer: StyleAndTextTuples | None = None,
        shortcuts: dict[str, Callable[[Command | None], None]] | None = None,
    ) -> None:
        """Open a command palette with the given commands."""
        if not self._app:
            return

        term_width, term_height = self._get_terminal_size()
        width, height = self._calculate_palette_size(term_width, term_height)

        palette = CommandPalette(
            commands=commands,
            on_close=self.close,
            height=height,
            footer=footer,
            shortcuts=shortcuts,
        )
        self._push(palette, width=width)
        self._state.palette_open = True
        self._invalidate()

    def open_dialog(
        self,
        provider: str,
        on_submit: Callable[[str], None],
    ) -> None:
        """Open an API key dialog for a provider."""
        term_width = shutil.get_terminal_size().columns
        width = max(40, min(60, term_width // 2))

        dialog = ApiKeyDialog(
            provider=provider,
            on_submit=on_submit,
            on_cancel=self.close,
        )
        self._push(dialog, width=width)

    def open_confirm(
        self,
        message: str,
        on_confirm: Callable[[], None],
    ) -> None:
        """Open a yes/no confirmation dialog."""
        term_width = shutil.get_terminal_size().columns
        width = max(40, min(60, term_width // 2))

        dialog = ConfirmDialog(
            message=message,
            on_confirm=on_confirm,
            on_cancel=self.close,
        )
        self._push(dialog, width=width)

    def replace_top(
        self,
        n: int,
        commands: list[Command],
        *,
        footer: StyleAndTextTuples | None = None,
        shortcuts: dict[str, Callable[[Command | None], None]] | None = None,
    ) -> None:
        """Pop *n* overlays and push a new palette in one operation."""
        for _ in range(min(n, len(self._stack))):
            self._stack.pop()
        self._floats.clear()
        self.open_palette(commands, footer=footer, shortcuts=shortcuts)

    def close(self) -> None:
        """Close the top overlay (Escape handler)."""
        if not self._stack:
            return

        self._stack.pop()
        self._floats.clear()

        if self._stack:
            prev_content, prev_float = self._stack[-1]
            self._floats.append(prev_float)
            self._focus_content(prev_content)
        elif self._app:
            self._app.layout.focus(self._layout.input_area.buffer)

        self._state.palette_open = self._is_open
        self._invalidate()

    def close_all(self) -> None:
        """Close all overlays."""
        self._stack.clear()
        self._floats.clear()
        self._state.palette_open = False

        if self._app:
            self._app.layout.focus(self._layout.input_area.buffer)

        self._invalidate()
