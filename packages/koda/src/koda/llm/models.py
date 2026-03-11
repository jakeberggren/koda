from enum import StrEnum, auto

from pydantic import BaseModel, Field


class ThinkingLevel(StrEnum):
    NONE = auto()
    MINIMAL = auto()
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    XHIGH = auto()


class ModelCapabilities(StrEnum):
    WEB_SEARCH = auto()
    EXTENDED_PROMPT_RETENTION = auto()


class ModelDefinition(BaseModel):
    id: str
    name: str
    provider: str
    thinking: set[ThinkingLevel] = Field(default_factory=set)
    capabilities: set[ModelCapabilities] = Field(default_factory=set)
