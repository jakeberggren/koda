"""Style definitions for Koda TUI."""

from prompt_toolkit.styles import Style

TUI_DARK_STYLE = Style.from_dict(
    {
        # Chat area
        "chat-area": "",
        # Separators
        "separator": "fg:ansibrightblack",
        # Input prompt
        "prompt": "bold ansimagenta",
        # Status bar
        "status-bar": "fg:ansibrightblack",
        "status-bar.left": "fg:ansibrightblack",
        "status-bar.right": "fg:ansimagenta",
        # Scrollbar
        "scrollbar.track": "fg:ansibrightblack",
        "scrollbar.thumb": "fg:ansiwhite",
        # Error display
        "error": "fg:ansired bold",
        # Queued inputs
        "queued-inputs": "fg:ansibrightblack bg:#4e4e4e italic",
        "queued-inputs.title": "bold noitalic",
        # Command palette
        "palette.frame": "fg:ansibrightblack bg:default",
        "palette.box": "bg:default",
        "palette.title": "fg:ansiwhite bold",
        "palette.prompt": "bold ansimagenta",
        "palette.hint": "fg:ansibrightblack",
        "palette.separator": "fg:ansibrightblack",
        "palette.item": "fg:ansiwhite",
        "palette.selected": "bg:ansimagenta fg:ansiwhite bold",
        "palette.empty": "fg:ansibrightblack italic",
        "palette.dim": "fg:ansibrightblack",
        "palette.group": "fg:ansibrightblack bold",
        # Dialog
        "dialog.frame": "fg:ansibrightblack bg:default",
        "dialog.box": "bg:default",
        "dialog.title": "fg:ansiwhite bold bg:default",
        "dialog.hint": "fg:ansibrightblack bg:default",
        "dialog.button": "fg:ansibrightblack bg:default",
        "dialog.selected": "bg:ansimagenta fg:ansiwhite bold",
    }
)

TUI_LIGHT_STYLE = Style.from_dict(
    {
        # Chat area
        "chat-area": "",  # explicit is better
        # Separators
        "separator": "fg:ansibrightblack",
        # Input prompt
        "prompt": "bold ansimagenta",
        # Status bar
        "status-bar": "fg:ansiblack",
        "status-bar.left": "fg:ansiblack",
        "status-bar.right": "fg:ansimagenta",
        # Scrollbar
        "scrollbar.track": "fg:ansigray",
        "scrollbar.thumb": "fg:ansibrightblack",
        # Error display
        "error": "fg:ansired bold",
        # Queued inputs
        "queued-inputs": "fg:ansibrightblack bg:#e4e4e4 italic",
        "queued-inputs.title": "bold noitalic",
        # Command palette
        "palette.frame": "fg:ansibrightblack bg:default",
        "palette.box": "bg:default",
        "palette.title": "fg:ansiblack bold",
        "palette.prompt": "bold ansimagenta",
        "palette.hint": "fg:ansibrightblack",
        "palette.separator": "fg:ansibrightblack",
        "palette.item": "fg:ansiblack",
        "palette.selected": "bg:ansimagenta fg:ansiwhite bold",
        "palette.empty": "fg:ansibrightblack italic",
        "palette.dim": "fg:ansibrightblack",
        "palette.group": "fg:ansimagenta bold",
        # Dialog
        "dialog.frame": "fg:ansibrightblack bg:default",
        "dialog.box": "bg:default",
        "dialog.title": "fg:ansiblack bold bg:default",
        "dialog.hint": "fg:ansibrightblack bg:default",
        "dialog.button": "fg:ansibrightblack bg:default",
        "dialog.selected": "bg:ansimagenta fg:ansiwhite bold",
    }
)


def get_style(theme: str) -> Style:
    """Return the style for the requested theme."""
    if theme == "light":
        return TUI_LIGHT_STYLE
    return TUI_DARK_STYLE
