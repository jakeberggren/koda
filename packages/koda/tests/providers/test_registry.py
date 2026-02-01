"""Tests for providers/registry.py - registry operations."""

import pytest

from koda.providers import exceptions
from koda.providers.registry import ModelDefinition, ModelRegistry, ProviderRegistry
from koda_common.settings import SettingsManager


class DummySettingsStore:
    def load(self) -> dict[str, object]:
        return {}

    def save(self, data: dict[str, object]) -> None:
        return None


class DummySecretsStore:
    def get_key(self, key: str) -> str | None:
        return None

    def set_key(self, key: str, value: str) -> None:
        return None

    def delete_key(self, key: str) -> None:
        return None


class DummyProvider:
    def __init__(self, settings: object, model: str | None) -> None:
        self.settings = settings
        self.model = model
        self.adapter = None


def make_provider_factory(calls: list[tuple[object, str | None]]):
    def factory(settings: object, model: str | None) -> DummyProvider:
        calls.append((settings, model))
        return DummyProvider(settings, model)

    return factory


def make_model(
    model_id: str,
    name: str,
    provider: str,
) -> ModelDefinition:
    return ModelDefinition(id=model_id, name=name, provider=provider)


class TestProviderRegistry:
    """Tests for ProviderRegistry operations."""

    @pytest.fixture
    def registry(self) -> ProviderRegistry:
        return ProviderRegistry()

    @pytest.fixture
    def settings_manager(self) -> SettingsManager:
        return SettingsManager(
            settings_store=DummySettingsStore(),
            secrets_store=DummySecretsStore(),
        )

    def test_register_and_create(
        self,
        registry: ProviderRegistry,
        settings_manager: SettingsManager,
    ) -> None:
        """Providers can be registered and created by name."""
        calls: list[tuple[object, str | None]] = []
        factory = make_provider_factory(calls)

        registry.register("OpenAI", factory)

        provider = registry.create(" openai ", settings_manager, " gpt-4 ")

        assert isinstance(provider, DummyProvider)
        assert provider.settings is settings_manager
        assert provider.model == "gpt-4"
        assert calls == [(settings_manager, "gpt-4")]

    def test_duplicate_registration_raises(self, registry: ProviderRegistry) -> None:
        """Registering the same provider twice raises ProviderAlreadyRegisteredError."""
        registry.register("openai", make_provider_factory([]))

        with pytest.raises(exceptions.ProviderAlreadyRegisteredError) as exc_info:
            registry.register(" OpenAI ", make_provider_factory([]))

        assert exc_info.value.provider_name == "openai"

    def test_empty_name_raises(self, registry: ProviderRegistry) -> None:
        """Empty provider names raise ProviderNameEmptyError."""
        with pytest.raises(exceptions.ProviderNameEmptyError):
            registry.register("   ", make_provider_factory([]))

    def test_create_unknown_provider_raises(
        self,
        registry: ProviderRegistry,
        settings_manager: SettingsManager,
    ) -> None:
        """Unknown providers raise ProviderNotSupportedError."""
        with pytest.raises(exceptions.ProviderNotSupportedError) as exc_info:
            registry.create("unknown", settings_manager)

        assert exc_info.value.provider_name == "unknown"

    def test_supported_sorted(self, registry: ProviderRegistry) -> None:
        """supported returns normalized provider names in sorted order."""
        registry.register("OpenAI", make_provider_factory([]))
        registry.register("Anthropic", make_provider_factory([]))

        assert registry.supported() == ["anthropic", "openai"]


class TestModelRegistry:
    """Tests for ModelRegistry operations."""

    @pytest.fixture
    def registry(self) -> ModelRegistry:
        return ModelRegistry()

    def test_register_and_get(self, registry: ModelRegistry) -> None:
        """Models can be registered and retrieved by id."""
        model = make_model("gpt-4", "GPT-4", "openai")

        registry.register(model)

        retrieved = registry.get("gpt-4")

        assert retrieved is model

    def test_register_all(self, registry: ModelRegistry) -> None:
        """Multiple models can be registered at once."""
        models = [
            make_model("gpt-4", "GPT-4", "openai"),
            make_model("claude-3", "Claude 3", "anthropic"),
        ]

        registry.register_all(models)

        assert registry.get("gpt-4") is models[0]
        assert registry.get("claude-3") is models[1]

    def test_duplicate_registration_raises(self, registry: ModelRegistry) -> None:
        """Registering the same model twice raises ModelAlreadyRegisteredError."""
        registry.register(make_model("gpt-4", "GPT-4", "openai"))

        with pytest.raises(exceptions.ModelAlreadyRegisteredError) as exc_info:
            registry.register(make_model(" GPT-4 ", "GPT-4", "openai"))

        assert exc_info.value.model_name == "GPT-4"
        assert exc_info.value.provider_name == "openai"

    def test_empty_id_raises(self, registry: ModelRegistry) -> None:
        """Empty model ids raise ModelConfigurationError."""
        with pytest.raises(exceptions.ModelConfigurationError):
            registry.register(make_model("   ", "No ID", "openai"))

    def test_get_unknown_id_raises(self, registry: ModelRegistry) -> None:
        """Unknown ids raise ModelNotSupportedError."""
        with pytest.raises(exceptions.ModelNotSupportedError) as exc_info:
            registry.get("unknown-model")

        assert exc_info.value.provider_model == "unknown-model"
        assert exc_info.value.provider_name == "unknown"

    def test_supported_filters_by_provider(self, registry: ModelRegistry) -> None:
        """supported can filter by provider name."""
        registry.register(make_model("gpt-4", "GPT-4", "OpenAI"))
        registry.register(make_model("claude-3", "Claude 3", "Anthropic"))
        registry.register(make_model("gpt-3.5", "GPT-3.5", "OpenAI"))

        supported = registry.supported(" openai ")

        assert [model.id for model in supported] == ["gpt-4", "gpt-3.5"]

    def test_id_normalization(self, registry: ModelRegistry) -> None:
        """Model ids are normalized for registration and lookup."""
        model = make_model("  GPT-4 ", "GPT-4", "openai")

        registry.register(model)

        assert registry.get("gpt-4") is model
        assert registry.get(" GPT-4 ") is model
