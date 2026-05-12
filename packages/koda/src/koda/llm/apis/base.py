from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from koda.llm import exceptions

if TYPE_CHECKING:
    from koda.llm.models import ProviderConfig, ProviderModelConfig
    from koda.llm.protocols import LLM
    from koda_common.settings import SettingsManager


@dataclass(frozen=True, slots=True)
class LLMApiContext:
    """Resolved catalog selection and settings used to construct an LLM API."""

    provider_id: str
    provider: ProviderConfig
    model: ProviderModelConfig
    settings: SettingsManager

    def require_api_key(self) -> str:
        """Return a normalized provider API key or raise a configuration error."""
        if (api_key := self.settings.get_api_key(self.provider_id)) is None:
            raise exceptions.ApiKeyNotConfiguredError(self.provider_id)
        normalized_api_key = api_key.strip()
        if not normalized_api_key:
            raise exceptions.EmptyApiKeyError(self.provider_id)
        return normalized_api_key

    def require_max_output_tokens(self) -> int:
        """Return the selected model's max output tokens or raise if missing."""
        if self.model.max_output_tokens is None:
            raise exceptions.ModelMaxOutputTokensMissingError(
                self.model.id,
                self.provider_id,
            )
        return self.model.max_output_tokens


class LLMApiFactory(Protocol):
    """Callable constructor registered for a model-catalog API id."""

    def __call__(
        self,
        context: LLMApiContext,
    ) -> LLM:
        """Create an LLM instance using the given provider and model."""
        ...
