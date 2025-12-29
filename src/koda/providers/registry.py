from __future__ import annotations

from collections.abc import Callable

from koda.config.settings import Settings
from koda.providers.base import Provider

type ProviderFactory = Callable[[Settings, str | None], Provider]


class ProviderRegistry:
    """Registry for provider factories."""

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        key = name.strip().lower()
        if not key:
            raise ValueError("Provider name cannot be empty")
        if key in self._factories:
            raise ValueError(f"Provider '{key}' is already registered")
        self._factories[key] = factory

    def create(self, name: str, settings: Settings, model: str | None = None) -> Provider:
        key = name.strip().lower()
        factory = self._factories.get(key)
        if factory is None:
            supported = ", ".join(self.supported()) or "(none)"
            raise ValueError(f"Provider '{key}' is not supported. Supported providers: {supported}")
        return factory(settings, model)

    def supported(self) -> list[str]:
        return sorted(self._factories.keys())


_registry = ProviderRegistry()


def get_provider_registry() -> ProviderRegistry:
    return _registry
