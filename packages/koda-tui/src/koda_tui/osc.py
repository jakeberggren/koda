"""Operating System Command (OSC) terminal queries."""

from __future__ import annotations

import contextlib
import os
import re
import select
import sys
import termios
import tty

RGBColor = tuple[int, int, int]
_OSC11_QUERY = "\033]11;?\033\\"
_OSC11_RESPONSE_RE = re.compile(
    r"\x1b\]11;rgb:([0-9a-fA-F]{2,4})/([0-9a-fA-F]{2,4})/([0-9a-fA-F]{2,4})(?:\x1b\\|\x07)"
)
_OSC11_TIMEOUT_SECONDS = 0.05


def parse_osc11(response: str) -> RGBColor | None:
    """Parse an OSC 11 terminal background color response."""
    match = _OSC11_RESPONSE_RE.search(response)
    if not match:
        return None

    components: list[int] = []
    for value in match.groups():
        max_value = (16 ** len(value)) - 1
        components.append(round(int(value, 16) * 255 / max_value))
    return (components[0], components[1], components[2])


def _read_osc11_response(fd: int) -> str:
    response = ""
    while select.select([fd], [], [], _OSC11_TIMEOUT_SECONDS)[0]:
        chunk = os.read(fd, 128).decode(errors="ignore")
        if not chunk:
            break
        response += chunk
        if parse_osc11(response) is not None:
            break
    return response


def query_osc11() -> RGBColor | None:
    """Best-effort OSC 11 query for the terminal background color.

    OSC query responses arrive on terminal input. Call this only before the
    prompt_toolkit application starts owning input.
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
        sys.stdout.write(_OSC11_QUERY)
        sys.stdout.flush()
        response = _read_osc11_response(fd)
    except OSError:
        return None
    finally:
        with contextlib.suppress(termios.error):
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)

    return parse_osc11(response)
