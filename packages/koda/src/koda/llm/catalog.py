from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import as_file, files
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, PlainValidator, ValidationError

from koda.llm import exceptions
from koda.llm.apis import LLMApi
from koda.llm.apis.codex import OpenAICodexResponsesAPI
from koda.llm.apis.completions import OpenAICompletionsAPI
from koda.llm.apis.messages import AnthropicMessagesAPI
from koda.llm.apis.responses import OpenAIResponsesAPI
from koda.llm.models import (
    AuthMethod,
    Connection,
    Model,
    Provider,
    ThinkingOption,
    ThinkingOptionId,
)
from koda_common.logging import get_logger
from koda_common.paths import model_overrides_file_path

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger(__name__)


# The models.json file format. It is grouped by connection; the catalog regroups it by model.

_APIS: dict[str, type[LLMApi]] = {
    "anthropic-messages": AnthropicMessagesAPI,
    "openai-responses": OpenAIResponsesAPI,
    "openai-completions": OpenAICompletionsAPI,
    "openai-codex-responses": OpenAICodexResponsesAPI,
}


class _UnknownApiError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"unknown api '{name}', expected one of: {', '.join(_APIS)}")


def _api(name: str) -> type[LLMApi]:
    """The API implementation named ``name`` in models.json."""
    try:
        return _APIS[name]
    except KeyError:
        raise _UnknownApiError(name) from None


class _ThinkingBudgetFile(BaseModel):
    min_tokens: int | None = None
    max_tokens: int | None = None


class _ThinkingModeFile(BaseModel):
    label: str
    description: str | None = None


class _ThinkingFile(BaseModel):
    modes: list[ThinkingOptionId] = Field(default_factory=list)
    budget_tokens: _ThinkingBudgetFile | None = None


class _ModelFile(BaseModel):
    id: str
    name: str
    detail: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    capabilities: dict[str, object] = Field(default_factory=dict)
    thinking: _ThinkingFile = Field(default_factory=_ThinkingFile)


class _ConnectionFile(BaseModel):
    auth: AuthMethod = "api-key"
    label: str | None = None
    detail: str | None = None
    description: str | None = None
    api: Annotated[type[LLMApi], PlainValidator(_api)]
    base_url: str
    capabilities: dict[str, object] = Field(default_factory=dict)
    models: list[_ModelFile] = Field(default_factory=list)


class _ProviderFile(BaseModel):
    name: str
    description: str | None = None
    connections: dict[str, _ConnectionFile]
    capabilities: dict[str, object] = Field(default_factory=dict)
    thinking_modes: dict[ThinkingOptionId, _ThinkingModeFile] = Field(default_factory=dict)


class _CatalogFile(BaseModel):
    providers: dict[str, _ProviderFile] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CatalogWarning:
    summary: str
    detail: str | None = None


def _normalize(value: str) -> str:
    """Normalize an id for case-insensitive lookup."""
    return value.strip().lower()


def _read(path: Path) -> _CatalogFile:
    return _CatalogFile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _merge(builtin: _CatalogFile, user: _CatalogFile | None) -> dict[str, _ProviderFile]:
    """The builtin providers, with user providers replacing those with the same id."""
    providers = {_normalize(id_): provider for id_, provider in builtin.providers.items()}
    for id_, provider in (user.providers if user else {}).items():
        providers[_normalize(id_)] = provider
    return providers


def _thinking_options(
    provider_id: str, provider: _ProviderFile, model: _ModelFile
) -> tuple[ThinkingOption, ...]:
    options = []
    for mode_id in model.thinking.modes:
        mode = provider.thinking_modes.get(mode_id)
        if mode is None:
            raise exceptions.ModelThinkingModeNotConfiguredError(model.id, provider_id, mode_id)
        options.append(ThinkingOption(id=mode_id, label=mode.label, description=mode.description))
    return tuple(options)


def _build_provider(provider_id: str, provider: _ProviderFile) -> tuple[Provider, list[Model]]:
    """The provider, and its models with the connections that offer each of them."""
    connections: list[Connection] = []
    model_files: dict[str, _ModelFile] = {}
    model_connections: dict[str, list[Connection]] = {}
    for connection_id, connection_file in provider.connections.items():
        connection = Connection(
            id=_normalize(connection_id),
            provider=provider_id,
            api=connection_file.api,
            base_url=connection_file.base_url,
            auth=connection_file.auth,
            label=connection_file.label,
            description=connection_file.description,
            detail=connection_file.detail,
            capabilities=provider.capabilities | connection_file.capabilities,
        )
        connections.append(connection)
        for model_file in connection_file.models:
            key = _normalize(model_file.id)
            model_files.setdefault(key, model_file)
            model_connections.setdefault(key, []).append(connection)

    models = []
    for key, model_file in model_files.items():
        budget = model_file.thinking.budget_tokens
        models.append(
            Model(
                id=model_file.id,
                name=model_file.name,
                provider=provider_id,
                detail=model_file.detail,
                context_window=model_file.context_window,
                max_output_tokens=model_file.max_output_tokens,
                thinking_options=_thinking_options(provider_id, provider, model_file),
                thinking_budget_tokens=budget.max_tokens if budget else None,
                capabilities=model_file.capabilities,
                # Prefer OAuth: a subscription over pay-per-token API keys.
                connections=tuple(sorted(model_connections[key], key=lambda c: c.auth != "oauth")),
            )
        )
    built = Provider(
        id=provider_id,
        name=provider.name,
        description=provider.description,
        connections=tuple(connections),
    )
    return built, models


class Catalog:
    """The providers and models Koda can use, from the bundled and user models.json."""

    def __init__(self, providers: dict[str, _ProviderFile]) -> None:
        self._providers: dict[str, Provider] = {}
        self._models: dict[tuple[str, str], Model] = {}
        for provider_id, provider_file in providers.items():
            provider, models = _build_provider(provider_id, provider_file)
            self._providers[provider_id] = provider
            for model in models:
                self._models[(provider_id, _normalize(model.id))] = model

    @classmethod
    def from_files(
        cls,
        builtin_path: Path,
        user_path: Path | None = None,
    ) -> tuple[Catalog, list[CatalogWarning]]:
        """Load the catalog; an invalid user file is ignored with a warning."""
        builtin = _read(builtin_path)
        if user_path is None or not user_path.exists():
            return cls(_merge(builtin, None)), []
        try:
            return cls(_merge(builtin, _read(user_path))), []
        except (
            json.JSONDecodeError,
            ValidationError,
            OSError,
            exceptions.LLMConfigurationError,
        ) as e:
            log.warning("llm_user_models_config_invalid", path=str(user_path), error=str(e))
            warning = CatalogWarning(
                summary="invalid models.json", detail=f"Ignoring {user_path}: {e}"
            )
            return cls(_merge(builtin, None)), [warning]

    @classmethod
    def load(cls) -> tuple[Catalog, list[CatalogWarning]]:
        """Load the bundled catalog, merged with ~/.koda/models.json if present."""
        with as_file(files("koda.llm").joinpath("models.json")) as builtin_path:
            return cls.from_files(builtin_path, model_overrides_file_path())

    def providers(self) -> list[Provider]:
        """All providers, in catalog order."""
        return list(self._providers.values())

    def provider(self, provider_id: str) -> Provider:
        """The provider with ``provider_id``."""
        provider = self._providers.get(_normalize(provider_id))
        if provider is None:
            raise exceptions.ProviderNotSupportedError(provider_id)
        return provider

    def models(self, provider_id: str | None = None) -> list[Model]:
        """All models, or those of ``provider_id``, in catalog order."""
        if provider_id is None:
            return list(self._models.values())
        target = _normalize(provider_id)
        return [model for (provider, _), model in self._models.items() if provider == target]

    def model(self, provider_id: str, model_id: str) -> Model:
        """The model ``model_id`` of ``provider_id``."""
        provider = self.provider(provider_id)
        model = self._models.get((provider.id, _normalize(model_id)))
        if model is None:
            raise exceptions.ModelNotSupportedError(model_id, provider_id)
        return model
