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
        # Error display
        "error": "fg:ansired bold",
    }
)
