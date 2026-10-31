"""Terminal: how Koda talks to the terminal it runs in, keys coming in, and focus and
background colour beyond keys."""

from koda_tui.terminal import keys
from koda_tui.terminal.protocol import Terminal, TerminalInput

__all__ = ["Terminal", "TerminalInput", "keys"]
