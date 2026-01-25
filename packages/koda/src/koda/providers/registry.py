from collections.abc import Callable

from koda.providers import Provider, exceptions
from koda_common import SettingsManager
from koda_common.logging import get_logger

logger = get_logger(__name__)

type ProviderFactory = Callable[[SettingsManager, str | None], Provider]


class ProviderRegistry:
    """Registry for provider factories."""

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        key = name.strip().lower()
        if not key:
            logger.warning("provider_registration_failed_empty_name")
            raise exceptions.ProviderNameEmptyError
        if key in self._factories:
            logger.warning("provider_already_registered", name=key)
            raise exceptions.ProviderAlreadyRegisteredError(key)
        self._factories[key] = factory

    def create(self, name: str, settings: SettingsManager, model: str | None = None) -> Provider:
        key = name.strip().lower()
        factory = self._factories.get(key)
        if factory is None:
            supported = ", ".join(self.supported()) or "(none)"
            logger.warning("provider_not_supported", name=key, supported=supported)
            raise exceptions.ProviderNotSupportedError(key)
        model = model.strip() if model and model.strip() else None
        logger.info("provider_created", name=key, model=model)
        return factory(settings, model)

    def supported(self) -> list[str]:
        return sorted(self._factories.keys())


_registry = ProviderRegistry()


def get_provider_registry() -> ProviderRegistry:
    return _registry
