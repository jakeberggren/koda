from enum import StrEnum, auto

from pydantic import BaseModel, Field


class ThinkingLevel(StrEnum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    EXTRA_HIGH = auto()


class ModelCapability(StrEnum):
    WEB_SEARCH = auto()
    EXTENDED_PROMPT_RETENTION = auto()


class ModelDefinition(BaseModel):
    id: str
    name: str
    provider: str
    thinking: set[ThinkingLevel] = Field(default_factory=set)
    capabilities: set[ModelCapability] = Field(default_factory=set)
