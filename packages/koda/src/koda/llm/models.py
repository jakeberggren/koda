from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field

type ThinkingOptionId = str


class ThinkingOption(BaseModel):
    id: ThinkingOptionId
    label: str
    description: str | None = None

    @classmethod
    def none(cls) -> Self:
        """Return the explicit no-thinking option."""
        return cls(id="none", label="none")


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

    @property
    def effective_thinking_options(self) -> tuple[ThinkingOption, ...]:
        """Return selectable thinking options with no-thinking as the fallback."""
        return tuple(self.thinking_options) or (ThinkingOption.none(),)

    @property
    def supports_thinking(self) -> bool:
        """Return whether this model supports any non-default thinking option."""
        return any(option.id != "none" for option in self.effective_thinking_options)

    def resolve_thinking_option(self, thinking_id: ThinkingOptionId) -> ThinkingOption:
        """Return the matching thinking option or the first effective option."""
        options = self.effective_thinking_options
        return next((option for option in options if option.id == thinking_id), options[0])


class ProviderThinkingBudgetConfig(BaseModel):
    min_tokens: int | None = None
    max_tokens: int | None = None


class ProviderThinkingModeConfig(BaseModel):
    label: str
    description: str | None = None


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
