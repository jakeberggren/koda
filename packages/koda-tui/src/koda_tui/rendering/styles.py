"""Style definitions for Koda TUI."""

from prompt_toolkit.styles import Style

TUI_STYLE = Style.from_dict(
    {
        # Chat area
        "chat-area": "",
        # Separators
        "separator": "fg:ansibrightblack",
        # Input prompt
        "prompt": "bold ansiblue",
        # Status bar
        "status-bar": "bg:ansiblue fg:ansiwhite",
        "status-bar.left": "bg:ansiblue fg:white bold",
        "status-bar.right": "bg:ansiblue fg:ansiyellow",
        # Scrollbar
        "scrollbar.track": "fg:ansibrightblack",
        "scrollbar.thumb": "fg:ansiwhite",
        # Error display
        "error": "fg:ansired bold",
        # Command palette
        "palette.box": "bg:ansiblack",
        "palette.title": "fg:ansiwhite bold",
        "palette.prompt": "bold ansiblue",
        "palette.separator": "fg:ansibrightblack",
        "palette.item": "",
        "palette.selected": "bg:ansiblue fg:ansiwhite bold",
        "palette.empty": "fg:ansibrightblack italic",
    }
)
