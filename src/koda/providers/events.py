from __future__ import annotations

from dataclasses import dataclass

from koda.tools.base import ToolCall


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ToolCallRequested:
    call: ToolCall


ProviderEvent = TextDelta | ToolCallRequested
