from types import SimpleNamespace

import pytest

from koda.llm.models import ModelDefinition as CoreModelDefinition
from koda.llm.models import ThinkingOption
from koda.llm.registry import ModelRegistry, ProviderRegistry
from koda_service.services.in_process.catalog import CatalogService


class StubProviderRegistry(ProviderRegistry):
    def supported(self) -> list[str]:
        return ["openai", "anthropic"]


def test_list_providers_delegates_to_registry() -> None:
    provider_registry = StubProviderRegistry()
    service = CatalogService(
        SimpleNamespace(
            provider_registry=provider_registry,
            model_registry=ModelRegistry(),
        )
    )

    assert service.list_providers() == ["openai", "anthropic"]


def test_list_models_maps_service_models(monkeypatch: pytest.MonkeyPatch) -> None:
    core_model = CoreModelDefinition(
        id="gpt-5.2",
        name="GPT 5.2",
        provider="openai",
        thinking_options=[
            ThinkingOption(
                id="high",
                label="High",
                description="High effort for complex tasks.",
            )
        ],
    )
    model_registry = ModelRegistry()
    monkeypatch.setattr(model_registry, "supported", lambda _provider=None: [core_model])
    service = CatalogService(
        SimpleNamespace(
            provider_registry=ProviderRegistry(),
            model_registry=model_registry,
        )
    )

    models = service.list_models("openai")

    assert len(models) == 1
    assert models[0].id == "gpt-5.2"
    assert models[0].thinking_options
