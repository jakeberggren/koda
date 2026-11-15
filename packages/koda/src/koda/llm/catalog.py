from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import as_file, files
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, PlainValidator, ValidationError
from structlog import get_logger

from koda.llm import exceptions
from koda.llm.apis import LLMApi, LLMApiContext
from koda.llm.apis.codex import OpenAICodexResponsesAPI
from koda.llm.apis.completions import OpenAICompletionsAPI
from koda.llm.apis.messages import AnthropicMessagesAPI
from koda.llm.apis.responses import OpenAIResponsesAPI
from koda.llm.auth.codex import OpenAICodexAuth
from koda.llm.models import (
    AuthMethod,
    Connection,
    Model,
    Provider,
    Thinking,
    ThinkingOption,
    ThinkingOptionId,
)
from koda.llm.utils import resolve_openai_client
from koda.paths import model_overrides_file_path

if TYPE_CHECKING:
    from pathlib import Path

    from koda.llm.auth.protocols import ProviderAuth
    from koda.llm.credentials import Credentials
    from koda.llm.protocols import LLM

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


# The browser login of each API that connects with OAuth instead of an API key.
OAUTH_LOGINS: dict[type[LLMApi], type[ProviderAuth]] = {OpenAICodexResponsesAPI: OpenAICodexAuth}


def _api(name: str) -> type[LLMApi]:
    """The API implementation named ``name`` in models.json."""
    try:
        return _APIS[name]
    except KeyError:
        raise _UnknownApiError(name) from None


class _ThinkingModeFile(BaseModel):
    label: str
    description: str | None = None


class _ThinkingFile(BaseModel):
    modes: list[ThinkingOptionId] = Field(default_factory=list)


class _ModelFile(BaseModel):
    id: str
    name: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    capabilities: dict[str, object] = Field(default_factory=dict)
    thinking: _ThinkingFile = Field(default_factory=_ThinkingFile)


class _ConnectionFile(BaseModel):
    auth: AuthMethod = "api-key"
    label: str | None = None
    detail: str = ""
    description: str | None = None
    api: Annotated[type[LLMApi], PlainValidator(_api)]
    base_url: str
    capabilities: dict[str, object] = Field(default_factory=dict)
    models: list[_ModelFile] = Field(default_factory=list)

    @property
    def oauth(self) -> ProviderAuth | None:
        """The browser login, for an OAuth connection."""
        if self.auth != "oauth":
            return None
        login = OAUTH_LOGINS.get(self.api)
        if login is None:
            raise exceptions.LLMConfigurationError(f"{self.api.__name__} has no browser login")
        return login()


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


def _thinking(provider_id: str, provider: _ProviderFile, model: _ModelFile) -> Thinking:
    """The model's thinking levels; only "none" when it declares none."""
    options = []
    for mode_id in model.thinking.modes:
        mode = provider.thinking_modes.get(mode_id)
        if mode is None:
            raise exceptions.LLMConfigurationError(
                f"Model '{model.id}' for provider {provider_id} references unknown thinking "
                f"mode '{mode_id}'"
            )
        options.append(ThinkingOption(id=mode_id, label=mode.label, description=mode.description))
    return Thinking(tuple(options)) if options else Thinking()


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
            oauth=connection_file.oauth,
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
        models.append(
            Model(
                id=model_file.id,
                name=model_file.name,
                provider=provider_id,
                context_window=model_file.context_window,
                max_output_tokens=model_file.max_output_tokens,
                thinking=_thinking(provider_id, provider, model_file),
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
    """The providers and models Koda can use, from the bundled and user models.json, and
    what of them ``credentials`` reach: ``connected``."""

    def __init__(self, providers: dict[str, _ProviderFile], credentials: Credentials) -> None:
        self._providers: dict[str, Provider] = {}
        self._models: dict[tuple[str, str], Model] = {}
        self._credentials = credentials
        for provider_id, provider_file in providers.items():
            provider, models = _build_provider(provider_id, provider_file)
            self._providers[provider_id] = provider
            for model in models:
                self._models[(provider_id, _normalize(model.id))] = model

    @classmethod
    def from_files(
        cls,
        credentials: Credentials,
        builtin_path: Path,
        user_path: Path | None = None,
    ) -> tuple[Catalog, list[CatalogWarning]]:
        """Load the catalog; an invalid user file is ignored with a warning."""
        builtin = _read(builtin_path)
        if user_path is None or not user_path.exists():
            return cls(_merge(builtin, None), credentials), []
        try:
            return cls(_merge(builtin, _read(user_path)), credentials), []
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
            return cls(_merge(builtin, None), credentials), [warning]

    @classmethod
    def load(cls, credentials: Credentials) -> tuple[Catalog, list[CatalogWarning]]:
        """Load the bundled catalog, merged with ~/.koda/models.json if present."""
        with as_file(files("koda.llm").joinpath("models.json")) as builtin_path:
            return cls.from_files(credentials, builtin_path, model_overrides_file_path())

    @property
    def connected(self) -> Connected:
        """What the credentials reach, as they are now: a login shows straight away.
        Reading it raises ``CredentialsError`` when the credentials can't be read."""
        return Connected(self, self._credentials)

    def providers(self) -> list[Provider]:
        """All providers, in catalog order."""
        return list(self._providers.values())

    def provider(self, provider_id: str) -> Provider:
        """The provider with ``provider_id``."""
        provider = self._providers.get(_normalize(provider_id))
        if provider is None:
            raise exceptions.ModelNotFound(f"Provider '{provider_id}' is not supported")
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
            raise exceptions.ModelNotFound(
                f"Model '{model_id}' for provider {provider_id} is not supported"
            )
        return model

    def resolve(self, provider_id: str | None, model_id: str | None) -> Model:
        """The model to use, or the ``ModelUnavailable`` that says why there's none."""
        if not self.connected.providers:
            raise exceptions.NoProviderConnected
        if provider_id is None or model_id is None:
            raise exceptions.NoModelSelected
        model = self.model(provider_id, model_id)
        if model not in self.connected:
            raise exceptions.ModelNotConnected(model.provider, model.id)
        return model

    async def connect(self, model: Model, *, tracing: bool = False) -> LLM:
        """An LLM for ``model``, over its first connected connection.

        With ``tracing``, OpenAI-compatible clients are traced to Langfuse.
        """
        connection = self.connected.connection(model)
        return await connection.api.from_context(
            LLMApiContext(
                model=model,
                connection=connection,
                credentials=self._credentials,
                openai_client=resolve_openai_client(tracing=tracing),
            )
        )


@dataclass(frozen=True, slots=True)
class Connected:
    """The part of a catalog its credentials reach. Each read asks the credentials anew."""

    _catalog: Catalog
    _credentials: Credentials

    @property
    def providers(self) -> list[Provider]:
        """Connected providers, in catalog order."""
        return [provider for provider in self._catalog.providers() if provider in self]

    @property
    def models(self) -> list[Model]:
        """Connected models, in catalog order."""
        return [model for model in self._catalog.models() if model in self]

    def connections(self, item: Provider | Model) -> list[Connection]:
        """The connected connections of ``item``, in its order of preference."""
        return [connection for connection in item.connections if connection in self]

    def connection(self, model: Model) -> Connection:
        """The connection to use for ``model``: its first connected one."""
        for connection in model.connections:
            if connection in self:
                return connection
        raise exceptions.ModelNotConnected(model.provider, model.id)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Connection):
            credential = self._credentials.get_credential(item.credential_key)
            return credential is not None and credential.auth_type == item.auth
        if isinstance(item, Provider | Model):
            return any(connection in self for connection in item.connections)
        return False
