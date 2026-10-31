"""The TUI stylesheet: maps semantic style classes to theme colors."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from prompt_toolkit.styles import Style

from koda_tui.design.terminal import is_light_background, surface_from_background
from koda_tui.design.themes import select_theme

if TYPE_CHECKING:
    from koda_tui.design.themes import Theme
    from koda_tui.osc import RGBColor


@cache
def style_for(setting: str, terminal_background: RGBColor | None) -> Style:
    """Return the stylesheet for a theme setting and the detected terminal background."""
    theme = select_theme(setting, terminal_background)
    return _stylesheet(theme, _surface(theme, terminal_background))


def _surface(theme: Theme, terminal_background: RGBColor | None) -> str:
    if (
        theme.derive_surface
        and terminal_background is not None
        and is_light_background(terminal_background) != theme.dark
    ):
        return surface_from_background(terminal_background)
    return theme.surface


def _stylesheet(theme: Theme, surface: str) -> Style:
    selection = f"bg:{theme.accent} fg:{theme.on_accent}"
    return Style.from_dict(
        {
            # Chat area
            "chat-area": "",
            # Separators
            "separator": "dim",
            # Input prompt
            "prompt": f"bold {theme.accent}",
            # Input area
            "input-area": f"bg:{surface}",
            # Status bar
            "status-bar": "",
            "status-bar.left": "dim",
            "status-bar.right": theme.accent,
            "status-bar.warning": theme.warning,
            "status-bar.muted": "dim",
            "status-bar.keybinding": "",
            "status-bar.thinking": theme.warning,
            "status-bar.spinner": theme.info,
            # Scrollbar
            "scrollbar.track": f"{surface} bg:{surface}",
            "scrollbar.thumb": theme.scrollbar,
            # Error display
            "error": f"{theme.error} bold",
            # Queued inputs
            "queued-inputs": "dim italic",
            "queued-inputs.title": "bold noitalic",
            # File discovery
            "file-discovery": "dim italic",
            "file-discovery.title": "bold noitalic",
            "file-discovery.item": "",
            "file-discovery.selected": f"nodim {selection} noitalic",
            "file-discovery.empty": "dim italic",
            # Command palette
            "palette.frame": "dim",
            "palette.box": "",
            # nodim keeps the title/items at full brightness even though the parent
            # frame sets "dim" (the dim attribute would otherwise cascade to children).
            "palette.title": "nodim bold",
            "palette.prompt": f"nodim bold {theme.accent}",
            "palette.hint": "dim",
            "palette.separator": "dim",
            "palette.marker": f"nodim {theme.accent} bold",
            "palette.current": f"nodim {theme.accent} bold",
            "palette.item": "nodim",
            "palette.selected": f"nodim {selection} bold",
            "palette.empty": "dim italic",
            "palette.dim": "dim",
            "palette.group": "dim bold",
            # Dialog
            "dialog": "bg:",
            "dialog.frame": "dim",
            "dialog.box": "",
            "dialog.title": "nodim bold",
            "dialog.hint": "dim",
            "dialog.button": "dim",
            "dialog.selected": f"nodim {selection} bold",
            # Chat messages
            "message.user": f"bg:{surface}",
            "diff.add": f"bg:{theme.diff_add}",
            "diff.remove": f"bg:{theme.diff_remove}",
            # Syntax highlighting
            **theme.syntax,
        }
    )
