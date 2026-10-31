"""Terminal background color helpers used to derive theme values."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from koda_tui.osc import RGBColor

_LUMINANCE_LIGHT_THRESHOLD = 0.5
_SURFACE_BLEND_AMOUNT = 0.125


def rgb_to_hex(color: RGBColor) -> str:
    """Format an RGB color for terminal rendering libraries."""
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def is_light_background(color: RGBColor) -> bool:
    """Return whether a terminal background color reads as light."""
    red, green, blue = color
    # Relative luminance in sRGB space is enough for light/dark background choice.
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    return luminance >= _LUMINANCE_LIGHT_THRESHOLD


def _blend_color(color: RGBColor, target: RGBColor, amount: float) -> RGBColor:
    return (
        round(color[0] + (target[0] - color[0]) * amount),
        round(color[1] + (target[1] - color[1]) * amount),
        round(color[2] + (target[2] - color[2]) * amount),
    )


def surface_from_background(background: RGBColor) -> str:
    """Derive a raised surface color by nudging the background toward contrast."""
    target = (0, 0, 0) if is_light_background(background) else (255, 255, 255)
    return rgb_to_hex(_blend_color(background, target, _SURFACE_BLEND_AMOUNT))
