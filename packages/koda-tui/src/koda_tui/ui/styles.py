"""Style definitions for Koda TUI."""

from prompt_toolkit.styles import Style

TUI_STYLE = Style.from_dict(
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
        # Command palette
        "palette.frame": "fg:ansibrightblack bg:ansiblack",
        "palette.box": "bg:ansiblack",
        "palette.title": "fg:ansiwhite bold",
        "palette.prompt": "bold ansimagenta",
        "palette.hint": "fg:ansibrightblack",
        "palette.separator": "fg:ansibrightblack",
        "palette.item": "fg:ansiwhite",
        "palette.selected": "bg:ansimagenta fg:ansiwhite bold",
        "palette.empty": "fg:ansibrightblack italic",
        "palette.dim": "fg:ansibrightblack",
        # Dialog
        "dialog.frame": "fg:ansibrightblack bg:ansiblack",
        "dialog.box": "bg:ansiblack",
        "dialog.title": "fg:ansiwhite bold bg:ansiblack",
        "dialog.hint": "fg:ansibrightblack bg:ansiblack",
    }
)
