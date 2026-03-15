from enum import StrEnum, auto

from pydantic import BaseModel, Field


class ModelCapability(StrEnum):
    WEB_SEARCH = auto()
    EXTENDED_PROMPT_RETENTION = auto()


type ThinkingOptionId = str
type ThinkingOptionLabel = str
type ThinkingOptionDescription = str


class ThinkingOption(BaseModel):
    id: ThinkingOptionId
    label: ThinkingOptionLabel
    description: ThinkingOptionDescription | None = None


class ModelDefinition(BaseModel):
    id: str
    name: str
    provider: str
    thinking_options: list[ThinkingOption] = Field(default_factory=list)
    capabilities: set[ModelCapability] = Field(default_factory=set)
