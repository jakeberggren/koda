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
    provider_features: dict[str, object] = Field(default_factory=dict)


class ModelDefinition(BaseModel):
    id: str
    name: str
    provider: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    thinking_options: list[ThinkingOption] = Field(default_factory=list)
    model_features: dict[str, object] = Field(default_factory=dict)
