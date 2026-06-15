"""Theme setting resolution for Koda TUI."""

from __future__ import annotations

import contextlib
import os
import re
import select
import sys
import termios
import tty
from dataclasses import dataclass
from functools import cache
from typing import Literal

from prompt_toolkit.styles import Style

ThemeSetting = Literal["auto", "dark", "light"]
ResolvedTheme = Literal["dark", "light"]
RGBColor = tuple[int, int, int]
_OSC_11_QUERY = "\033]11;?\033\\"
_OSC_11_RESPONSE_RE = re.compile(
    r"\x1b\]11;rgb:([0-9a-fA-F]{2,4})/([0-9a-fA-F]{2,4})/([0-9a-fA-F]{2,4})(?:\x1b\\|\x07)"
)
_OSC_11_TIMEOUT_SECONDS = 0.05
_LUMINANCE_LIGHT_THRESHOLD = 0.5
_SURFACE_BLEND_AMOUNT = 0.05
_FALLBACK_SURFACE_COLORS: dict[ResolvedTheme, RGBColor] = {
    "dark": (78, 78, 78),
    "light": (228, 228, 228),
}


@dataclass(frozen=True)
class TerminalTheme:
    """Resolved terminal theme and derived surface color."""

    theme: ResolvedTheme
    surface: RGBColor


_TUI_STYLE = {
    # Chat area
    "chat-area": "",
    # Separators
    "separator": "dim",
    # Input prompt
    "prompt": "bold ansimagenta",
    # Input area
    "input-area": "",
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
    "scrollbar.track": "",
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


def rgb_to_hex(color: RGBColor) -> str:
    """Format an RGB color for terminal rendering libraries."""
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def get_tui_style(theme: TerminalTheme) -> Style:
    """Return the prompt_toolkit style for the resolved terminal theme."""
    surface = rgb_to_hex(theme.surface)
    overrides = {
        "input-area": f"bg:{surface}",
        "scrollbar.track": f"{surface} bg:{surface}",
    }
    if theme.theme == "light":
        overrides["scrollbar.thumb"] = "ansibrightblack"
    return Style.from_dict({**_TUI_STYLE, **overrides})


def _theme_from_rgb(red: int, green: int, blue: int) -> ResolvedTheme:
    # Relative luminance in sRGB space is enough for light/dark background choice.
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    return "light" if luminance >= _LUMINANCE_LIGHT_THRESHOLD else "dark"


def _parse_osc_11_response(response: str) -> RGBColor | None:
    match = _OSC_11_RESPONSE_RE.search(response)
    if not match:
        return None

    components: list[int] = []
    for value in match.groups():
        max_value = (16 ** len(value)) - 1
        components.append(round(int(value, 16) * 255 / max_value))
    return (components[0], components[1], components[2])


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
def detect_terminal_background() -> RGBColor | None:
    """Best-effort terminal background color detection via OSC 11.

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
    detect_terminal_background.cache_clear()


def _blend_color(color: RGBColor, target: RGBColor, amount: float) -> RGBColor:
    return (
        round(color[0] + (target[0] - color[0]) * amount),
        round(color[1] + (target[1] - color[1]) * amount),
        round(color[2] + (target[2] - color[2]) * amount),
    )


def _surface_from_background(background: RGBColor) -> RGBColor:
    background_theme = _theme_from_rgb(*background)
    target = (255, 255, 255) if background_theme == "dark" else (0, 0, 0)
    return _blend_color(background, target, _SURFACE_BLEND_AMOUNT)


def resolve_theme(theme: ThemeSetting) -> TerminalTheme:
    """Resolve theme settings and derive a surface from the terminal background."""
    background = detect_terminal_background()
    if theme == "auto":
        resolved_theme = _theme_from_rgb(*background) if background is not None else "dark"
    else:
        resolved_theme = theme

    surface = (
        _surface_from_background(background)
        if background is not None
        else _FALLBACK_SURFACE_COLORS[resolved_theme]
    )
    return TerminalTheme(
        theme=resolved_theme,
        surface=surface,
    )
