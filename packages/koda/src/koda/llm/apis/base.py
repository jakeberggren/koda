from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from koda.llm.auth.registry import ProviderAuthRegistry
    from koda.llm.models import ProviderConfig, ProviderConnectionConfig, ProviderModelConfig
    from koda.llm.protocols import LLM
    from koda_common.settings import SettingsManager


@dataclass(frozen=True, slots=True)
class LLMApiContext:
    """Resolved catalog selection and settings used to construct an LLM API."""

    provider_id: str
    provider: ProviderConfig
    connection_id: str
    connection: ProviderConnectionConfig
    model: ProviderModelConfig
    settings: SettingsManager
    auth_registry: ProviderAuthRegistry


class LLMApiFactory(Protocol):
    """Callable constructor registered for a model-catalog API id."""

    async def __call__(
        self,
        context: LLMApiContext,
    ) -> LLM:
        """Create an LLM instance using the given provider and model."""
        ...
