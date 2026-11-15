from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from koda.messages import ToolMessage


def content_text(message: ToolMessage, key: str) -> str:
    """The string a tool put under ``key`` in its content."""
    value = message.output.content[key]
    assert isinstance(value, str)
    return value
