"""Keys: the keyboard as Koda reads it, naming modified keys and how terminals encode them."""

from __future__ import annotations

from string import ascii_lowercase

from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.keys import Keys

ALT_ENTER = (Keys.Escape, Keys.Enter)
ALT_UP = (Keys.Escape, Keys.Up)
ALT_DOWN = (Keys.Escape, Keys.Down)
COMMAND_UP = (Keys.Escape, Keys.Escape, Keys.Up)
COMMAND_DOWN = (Keys.Escape, Keys.Escape, Keys.Down)

SEQUENCES: dict[str, Keys | tuple[Keys, ...]] = {
    # Ctrl+letter and Escape: kitty keyboard protocol / CSI u.
    **{f"\x1b[{ord(letter)};5u": Keys[f"Control{letter.upper()}"] for letter in ascii_lowercase},
    "\x1b[27u": Keys.Escape,
    "\x1b[27;1u": Keys.Escape,
    # Word delete: Alt or Ctrl with Backspace.
    "\x1b\x7f": Keys.ControlW,
    "\x1b\b": Keys.ControlW,
    "\x1b[127;3u": Keys.ControlW,
    "\x1b[8;3u": Keys.ControlW,
    "\x1b[127;5u": Keys.ControlW,
    "\x1b[8;5u": Keys.ControlW,
    # Shift or Ctrl+Enter insert a newline; Alt+Enter is the alternate submit.
    "\x1b[13;5u": Keys.ControlJ,
    "\x1b[10;5u": Keys.ControlJ,
    "\x1b[13;2u": Keys.ControlJ,
    "\x1b[10;2u": Keys.ControlJ,
    "\x1b[27;2;13~": Keys.ControlJ,  # xterm
    "\x1b[13;3u": ALT_ENTER,
    "\x1b[10;3u": ALT_ENTER,
    "\x1b[27;3;13~": ALT_ENTER,
    "\x1b\r": ALT_ENTER,
    "\x1b\n": ALT_ENTER,
    # Alt+Up/Down. Plain ESC+[A/B stays the arrow keys.
    "\x1b[1;3A": ALT_UP,
    "\x1b[65;3u": ALT_UP,
    "\x1b[1;3B": ALT_DOWN,
    "\x1b[66;3u": ALT_DOWN,
    # Command+Up/Down, which prompt_toolkit doesn't know; mapped so they don't type text.
    "\x1b[1;1A": COMMAND_UP,
    "\x1b[1;1B": COMMAND_DOWN,
}


def register() -> None:
    """Teach prompt_toolkit the sequences above."""
    ANSI_SEQUENCES.update(SEQUENCES)
