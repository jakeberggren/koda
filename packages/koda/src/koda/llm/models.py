from typing import Literal

from pydantic import BaseModel, Field

type ThinkingOptionId = str
type ThinkingOptionLabel = str
type ThinkingOptionDescription = str


class ThinkingOption(BaseModel):
    id: ThinkingOptionId
    label: ThinkingOptionLabel
    description: ThinkingOptionDescription | None = None


class ProviderDefinition(BaseModel):
    id: str
    name: str
    description: str | None = None
    provider_features: dict[str, object] = Field(default_factory=dict)


class ModelDefinition(BaseModel):
    id: str
    name: str
    provider: str
    description: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    thinking_options: list[ThinkingOption] = Field(default_factory=list)
    model_features: dict[str, object] = Field(default_factory=dict)


class ProviderThinkingBudgetConfig(BaseModel):
    min_tokens: int | None = None
    max_tokens: int | None = None


class ProviderThinkingModeConfig(BaseModel):
    label: ThinkingOptionLabel
    description: ThinkingOptionDescription | None = None


class ProviderThinkingConfig(BaseModel):
    modes: list[ThinkingOptionId] = Field(default_factory=list)
    budget_tokens: ProviderThinkingBudgetConfig | None = None


class ProviderModelConfig(BaseModel):
    id: str
    name: str
    description: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    capabilities: dict[str, object] = Field(default_factory=dict)
    thinking: ProviderThinkingConfig = Field(default_factory=ProviderThinkingConfig)


class ProviderConfig(BaseModel):
    name: str
    description: str | None = None
    base_url: str
    api: Literal["anthropic-messages", "openai-responses", "openai-completions"]
    capabilities: dict[str, object] = Field(default_factory=dict)
    thinking_modes: dict[ThinkingOptionId, ProviderThinkingModeConfig] = Field(default_factory=dict)
    models: list[ProviderModelConfig] = Field(default_factory=list)


class ProvidersConfig(BaseModel):
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
