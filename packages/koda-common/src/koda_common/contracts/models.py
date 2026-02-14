from enum import StrEnum

from pydantic import BaseModel, Field


class ThinkingLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTRA_HIGH = "extra_high"


class ModelCapability(StrEnum):
    WEB_SEARCH = "web_search"


class ModelDefinition(BaseModel):
    id: str
    name: str
    provider: str
    thinking: set[ThinkingLevel] = Field(default_factory=set)
    capabilities: set[ModelCapability] = Field(default_factory=set)
