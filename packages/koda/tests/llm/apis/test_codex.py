from __future__ import annotations

from time import time
from typing import TYPE_CHECKING, cast

import pytest

from koda.llm import exceptions
from koda.llm.apis.base import LLMApiContext
from koda.llm.apis.codex import CODEX_BACKEND, CODEX_ORIGINATOR, OpenAICodexResponsesAPI
from koda.llm.apis.registry import LLMApiRegistry
from koda.llm.auth.registry import ProviderAuthRegistry
from koda.llm.models import ProviderConfig, ProviderConnectionConfig, ProviderModelConfig
from koda_common.settings.credentials import ApiKeyCredential, OAuthCredential, ProviderCredential

if TYPE_CHECKING:
    from collections.abc import Callable

    from openai import AsyncOpenAI

    from koda_common.settings import SettingsManager


class _FakeSettings:
    langfuse_tracing_enabled = False

    def __init__(self, credential: ProviderCredential | None) -> None:
        self._credential = credential

    def get_credential(self, provider: str) -> ProviderCredential | None:
        _ = provider
        return self._credential

    def set_credential(self, provider: str, credential: ProviderCredential) -> None:
        _ = provider
        self._credential = credential


class _FakeAuthProvider:
    id = "openai:oauth"

    def __init__(
        self,
        refreshed: OAuthCredential | None = None,
        refresh_error: Exception | None = None,
    ) -> None:
        self.refreshed = refreshed
        self.refresh_error = refresh_error
        self.refresh_calls: list[OAuthCredential] = []

    async def login(self, callbacks: object) -> OAuthCredential:
        _ = callbacks
        raise NotImplementedError

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        self.refresh_calls.append(credential)
        if self.refresh_error is not None:
            raise self.refresh_error
        return self.refreshed or credential


class _FakeOpenAIClient:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class _FakeClientFactory:
    def __init__(self) -> None:
        self.clients: list[_FakeOpenAIClient] = []

    def __call__(self, **kwargs: object) -> _FakeOpenAIClient:
        client = _FakeOpenAIClient(**kwargs)
        self.clients.append(client)
        return client


def _context(credential: ProviderCredential | None) -> LLMApiContext:
    return LLMApiContext(
        provider_id="openai",
        provider=ProviderConfig(
            name="OpenAI",
            connections={
                "oauth": ProviderConnectionConfig(
                    auth="oauth",
                    api="openai-codex-responses",
                    base_url="https://chatgpt.com/backend-api/codex",
                    capabilities={"web_search": True},
                )
            },
        ),
        connection_id="oauth",
        connection=ProviderConnectionConfig(
            auth="oauth",
            api="openai-codex-responses",
            base_url="https://chatgpt.com/backend-api/codex",
            capabilities={"web_search": True},
        ),
        model=ProviderModelConfig(
            id="gpt-5.5",
            name="gpt-5.5",
            capabilities={"extended_prompt_retention": True},
        ),
        settings=cast("SettingsManager", _FakeSettings(credential)),
        auth_registry=ProviderAuthRegistry({"openai:oauth": _FakeAuthProvider()}),
    )


def test_registry_includes_openai_codex_responses_api() -> None:
    assert LLMApiRegistry.default().get("openai-codex-responses") is not None


async def test_codex_responses_factory_builds_oauth_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _FakeClientFactory()
    monkeypatch.setattr(
        "koda.llm.apis.codex.resolve_openai_client",
        cast("Callable[[object], Callable[..., AsyncOpenAI]]", lambda _settings: factory),
    )

    api = await OpenAICodexResponsesAPI.from_context(
        _context(
            OAuthCredential(
                type="oauth",
                access_token="access-token",  # noqa: S106
                refresh_token="refresh-token",  # noqa: S106
                expires_at=str(int(time()) + 3600),
                metadata={"chatgpt_account_id": "account-id"},
            )
        )
    )

    assert api.config.backend == CODEX_BACKEND
    assert api.config.web_search is True
    assert api.config.extended_prompt_retention is True
    assert len(factory.clients) == 1
    assert factory.clients[0].kwargs == {
        "api_key": "access-token",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "default_headers": {
            "chatgpt-account-id": "account-id",
            "originator": CODEX_ORIGINATOR,
        },
    }


async def test_codex_responses_factory_requires_oauth_credential() -> None:
    with pytest.raises(exceptions.OAuthCredentialRequiredError):
        await OpenAICodexResponsesAPI.from_context(
            _context(ApiKeyCredential(type="api_key", value="api-key"))
        )


async def test_codex_responses_factory_requires_account_id() -> None:
    with pytest.raises(exceptions.OAuthAccountIdMissingError):
        await OpenAICodexResponsesAPI.from_context(
            _context(
                OAuthCredential(
                    type="oauth",
                    access_token="access-token",  # noqa: S106
                    refresh_token="refresh-token",  # noqa: S106
                    expires_at=str(int(time()) + 3600),
                )
            )
        )


async def test_codex_responses_factory_refreshes_expired_oauth_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _FakeClientFactory()
    monkeypatch.setattr(
        "koda.llm.apis.codex.resolve_openai_client",
        cast("Callable[[object], Callable[..., AsyncOpenAI]]", lambda _settings: factory),
    )
    expired = OAuthCredential(
        type="oauth",
        access_token="expired-access-token",  # noqa: S106
        refresh_token="old-refresh-token",  # noqa: S106
        expires_at="1",
        metadata={"chatgpt_account_id": "old-account-id"},
    )
    refreshed = OAuthCredential(
        type="oauth",
        access_token="fresh-access-token",  # noqa: S106
        refresh_token="new-refresh-token",  # noqa: S106
        expires_at=str(int(time()) + 3600),
        metadata={"chatgpt_account_id": "fresh-account-id"},
    )
    settings = _FakeSettings(expired)
    auth_provider = _FakeAuthProvider(refreshed)
    context = _context(expired)
    context = LLMApiContext(
        provider_id=context.provider_id,
        provider=context.provider,
        connection_id=context.connection_id,
        connection=context.connection,
        model=context.model,
        settings=cast("SettingsManager", settings),
        auth_registry=ProviderAuthRegistry({"openai:oauth": auth_provider}),
    )

    api = await OpenAICodexResponsesAPI.from_context(context)

    assert auth_provider.refresh_calls == [expired]
    assert settings.get_credential("openai:oauth") == refreshed
    assert api.config.api_key == "fresh-access-token"
    assert factory.clients[0].kwargs["default_headers"] == {
        "chatgpt-account-id": "fresh-account-id",
        "originator": CODEX_ORIGINATOR,
    }


async def test_codex_responses_factory_translates_oauth_refresh_failure() -> None:
    expired = OAuthCredential(
        type="oauth",
        access_token="expired-access-token",  # noqa: S106
        refresh_token="old-refresh-token",  # noqa: S106
        expires_at="1",
    )
    context = _context(expired)
    context = LLMApiContext(
        provider_id=context.provider_id,
        provider=context.provider,
        connection_id=context.connection_id,
        connection=context.connection,
        model=context.model,
        settings=context.settings,
        auth_registry=ProviderAuthRegistry(
            {"openai:oauth": _FakeAuthProvider(refresh_error=RuntimeError("refresh failed"))}
        ),
    )

    with pytest.raises(exceptions.LLMAuthenticationError, match="refresh failed"):
        await OpenAICodexResponsesAPI.from_context(context)
