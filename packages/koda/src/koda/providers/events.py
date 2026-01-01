from dataclasses import dataclass

from koda.tools import ToolCall


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ToolCallRequested:
    call: ToolCall


ProviderEvent = TextDelta | ToolCallRequested
