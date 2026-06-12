"""Theme setting resolution for Koda TUI."""

from __future__ import annotations

import contextlib
import os
import re
import select
import sys
import termios
import tty
from functools import cache
from typing import Literal

from prompt_toolkit.styles import Style

ThemeSetting = Literal["auto", "dark", "light"]
ResolvedTheme = Literal["dark", "light"]
_OSC_11_QUERY = "\033]11;?\033\\"
_OSC_11_RESPONSE_RE = re.compile(
    r"\x1b\]11;rgb:([0-9a-fA-F]{2,4})/([0-9a-fA-F]{2,4})/([0-9a-fA-F]{2,4})(?:\x1b\\|\x07)"
)
_OSC_11_TIMEOUT_SECONDS = 0.05
_LUMINANCE_LIGHT_THRESHOLD = 0.5

_TUI_STYLE = {
    # Chat area
    "chat-area": "",
    # Separators
    "separator": "dim",
    # Input prompt
    "prompt": "bold ansimagenta",
    # Input area
    "input-area": "bg:#4e4e4e",
    # Status bar
    "status-bar": "",
    "status-bar.left": "dim",
    "status-bar.right": "ansimagenta",
    "status-bar.warning": "ansiyellow",
    "status-bar.muted": "dim",
    "status-bar.keybinding": "",
    "status-bar.thinking": "ansiyellow",
    "status-bar.spinner": "ansicyan",
    # Scrollbar
    "scrollbar.track": "dim",
    "scrollbar.thumb": "ansiwhite",
    # Error display
    "error": "ansired bold",
    # Queued inputs
    "queued-inputs": "dim italic",
    "queued-inputs.title": "bold noitalic",
    # File discovery
    "file-discovery": "dim italic",
    "file-discovery.title": "bold noitalic",
    "file-discovery.item": "",
    "file-discovery.selected": "nodim bg:ansimagenta fg:ansiwhite noitalic",
    "file-discovery.empty": "dim italic",
    # Command palette
    "palette.frame": "dim",
    "palette.box": "",
    # nodim keeps the title/items at full brightness even though the parent
    # frame sets "dim" (the dim attribute would otherwise cascade to children).
    "palette.title": "nodim bold",
    "palette.prompt": "nodim bold ansimagenta",
    "palette.hint": "dim",
    "palette.separator": "dim",
    "palette.marker": "nodim ansimagenta bold",
    "palette.current": "nodim ansimagenta bold",
    "palette.item": "nodim",
    "palette.selected": "nodim bg:ansimagenta fg:ansiwhite bold",
    "palette.empty": "dim italic",
    "palette.dim": "dim",
    "palette.group": "dim bold",
    # Dialog
    "dialog.frame": "dim",
    "dialog.box": "",
    "dialog.title": "nodim bold",
    "dialog.hint": "dim",
    "dialog.button": "dim",
    "dialog.selected": "bg:ansimagenta fg:ansiwhite bold",
}

TUI_DARK_STYLE = Style.from_dict(_TUI_STYLE)
TUI_LIGHT_STYLE = Style.from_dict(
    {
        **_TUI_STYLE,
        "input-area": "bg:#e4e4e4",
        "scrollbar.track": "ansigray",
        "scrollbar.thumb": "ansibrightblack",
    }
)


def get_tui_style(theme: ResolvedTheme) -> Style:
    """Return the prompt_toolkit style for the resolved terminal theme."""
    return TUI_LIGHT_STYLE if theme == "light" else TUI_DARK_STYLE


def _theme_from_rgb(red: int, green: int, blue: int) -> ResolvedTheme:
    # Relative luminance in sRGB space is enough for light/dark background choice.
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    return "light" if luminance >= _LUMINANCE_LIGHT_THRESHOLD else "dark"


def _parse_osc_11_response(response: str) -> ResolvedTheme | None:
    match = _OSC_11_RESPONSE_RE.search(response)
    if not match:
        return None

    components = []
    for value in match.groups():
        max_value = (16 ** len(value)) - 1
        components.append(round(int(value, 16) * 255 / max_value))
    return _theme_from_rgb(*components)


def _read_osc_11_response(fd: int) -> str:
    response = ""
    while select.select([fd], [], [], _OSC_11_TIMEOUT_SECONDS)[0]:
        chunk = os.read(fd, 128).decode(errors="ignore")
        if not chunk:
            break
        response += chunk
        if _parse_osc_11_response(response) is not None:
            break
    return response


@cache
def detect_terminal_theme() -> ResolvedTheme | None:
    """Best-effort terminal background brightness detection via OSC 11.

    OSC 11 queries the terminal's default background RGB color. Not every
    terminal responds, so callers should provide a fallback when this returns
    None.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return None

    fd = sys.stdin.fileno()
    try:
        old_attrs = termios.tcgetattr(fd)
    except termios.error:
        return None

    try:
        tty.setcbreak(fd)
        sys.stdout.write(_OSC_11_QUERY)
        sys.stdout.flush()
        response = _read_osc_11_response(fd)
    except OSError:
        return None
    finally:
        with contextlib.suppress(termios.error):
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)

    return _parse_osc_11_response(response)


def refresh_terminal_theme_detection() -> None:
    """Clear cached terminal theme detection so auto mode can re-query."""
    detect_terminal_theme.cache_clear()


def resolve_theme(theme: ThemeSetting) -> ResolvedTheme:
    """Resolve a persisted theme setting to a concrete renderer theme."""
    if theme == "auto":
        return detect_terminal_theme() or "dark"
    return theme
