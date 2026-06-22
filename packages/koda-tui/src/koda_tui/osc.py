"""Operating System Command (OSC) terminal queries."""

from __future__ import annotations

import re

RGBColor = tuple[int, int, int]
OSC_BEL = "\x07"
OSC_STRING_TERMINATOR = "\x1b\\"
OSC11_QUERY = "\033]11;?\033\\"

# Regex matching any OSC 11 terminal background color response.
OSC11_RESPONSE_RE = re.compile(
    "^"
    + re.escape("\x1b]11;rgb:")
    + r"([0-9a-fA-F]{2,4})/([0-9a-fA-F]{2,4})/([0-9a-fA-F]{2,4})"
    + r"(?:"
    + re.escape(OSC_STRING_TERMINATOR)
    + "|"
    + re.escape(OSC_BEL)
    + r")\Z"
)
OSC11_RESPONSE_START = "\x1b]11;rgb:"

# Regex matching any valid prefix of an OSC 11 response after the fixed start.
# The final string terminator can arrive as "\x1b\\" split across input reads.
OSC11_PREFIX_RE = re.compile(
    "^"
    + re.escape(OSC11_RESPONSE_START)
    + r"[0-9a-fA-F]{0,4}(?:/[0-9a-fA-F]{0,4}"
    + r"(?:/[0-9a-fA-F]{0,4}(?:\x1b?)?)?)?\Z"
)


def parse_osc11(response: str) -> RGBColor | None:
    """Parse an OSC 11 terminal background color response."""
    match = OSC11_RESPONSE_RE.search(response)
    if not match:
        return None

    components: list[int] = []
    for value in match.groups():
        max_value = (16 ** len(value)) - 1
        components.append(round(int(value, 16) * 255 / max_value))
    return (components[0], components[1], components[2])


def is_osc11_response_prefix(prefix: str) -> bool:
    """Return whether text is a partial OSC 11 response."""
    return (
        len(prefix) > 1
        and parse_osc11(prefix) is None
        and (OSC11_RESPONSE_START.startswith(prefix) or bool(OSC11_PREFIX_RE.match(prefix)))
    )
