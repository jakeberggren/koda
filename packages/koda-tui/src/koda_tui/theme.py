"""Theme setting resolution for Koda TUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from prompt_toolkit.styles import Style

if TYPE_CHECKING:
    from koda_tui.osc import RGBColor

ThemeSetting = Literal["auto", "dark", "light"]
ResolvedTheme = Literal["dark", "light"]
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


def resolve_theme(
    theme: ThemeSetting,
    terminal_background: RGBColor | None,
) -> TerminalTheme:
    """Resolve theme settings and derive a surface from the terminal background."""
    if theme == "auto":
        resolved_theme = (
            _theme_from_rgb(*terminal_background) if terminal_background is not None else "dark"
        )
    else:
        resolved_theme = theme

    surface = (
        _surface_from_background(terminal_background)
        if terminal_background is not None
        else _FALLBACK_SURFACE_COLORS[resolved_theme]
    )
    return TerminalTheme(
        theme=resolved_theme,
        surface=surface,
    )
