"""Tests for the provider menu: picking how to connect, API keys, and browser logins."""

# ruff: noqa: SLF001 - the login task is private

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import pytest

from koda.llm import Connected, Connection, Model, Provider
from koda.llm.apis.codex import OpenAICodexResponsesAPI
from koda.llm.apis.responses import OpenAIResponsesAPI
from koda.llm.credentials import ApiKeyCredential, OAuthCredential, ProviderCredential
from koda_tui import strings
from koda_tui.palette.context import PaletteContext
from koda_tui.palette.menus.providers import ProviderMenu
from koda_tui.ui.widgets import InputDialog, MessageDialog, Picker

if TYPE_CHECKING:
    from tests.palette.conftest import Overlays

    from koda.llm import Catalog
    from koda.llm.auth.protocols import OAuthLoginCallbacks
    from koda.sessions import SessionStore
    from koda_tui.outbox import Outbox
    from koda_tui.state import AppState
    from koda_tui.terminal import Terminal
    from koda_tui.ui.overlays import Overlays as RealOverlays


class _Credentials(dict[str, ProviderCredential]):
    def get_credential(self, key: str) -> ProviderCredential | None:
        return self.get(key)

    def set_credential(self, key: str, credential: ProviderCredential) -> None:
        self[key] = credential


class _FakeCatalog:
    """OpenAI, with one model, and what ``credentials`` reach of it."""

    def __init__(self, credentials: _Credentials) -> None:
        self._credentials = credentials

    @property
    def connected(self) -> Connected:
        return Connected(cast("Catalog", self), self._credentials)

    def providers(self) -> list[Provider]:
        return [_openai_provider(_BrowserLogin())]

    def models(self, provider: str | None = None) -> list[Model]:
        _ = provider
        return [Model(id="gpt-5.5", name="gpt-5.5", provider="openai")]


@pytest.fixture
def opened_urls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    urls: list[str] = []
    monkeypatch.setattr("webbrowser.open", urls.append)
    return urls


def _credential() -> OAuthCredential:
    return OAuthCredential(
        type="oauth",
        access_token="access-token",  # noqa: S106
        refresh_token="refresh-token",  # noqa: S106
        expires_at="123",
        metadata={"chatgpt_account_id": "account-id"},
    )


class _BrowserLogin:
    """Logs in once the browser comes back."""

    id = "openai:oauth"

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
        callbacks.on_auth_url("https://auth.example")
        return _credential()

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        return credential


class _PromptedLogin(_BrowserLogin):
    """Logs in with what is pasted into the prompt."""

    def __init__(self) -> None:
        self.answer: str | None = None

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
        callbacks.on_auth_url("https://auth.example")
        self.answer = await callbacks.on_prompt("Paste the callback URL")
        return _credential()


class _FailingLogin(_BrowserLogin):
    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
        _ = callbacks
        raise RuntimeError("token exchange failed")


def _menu(overlays: Overlays, credentials: _Credentials, state: AppState) -> ProviderMenu:
    context = PaletteContext(
        overlays=cast("RealOverlays", overlays),
        catalog=cast("Catalog", _FakeCatalog(credentials)),
        credentials=credentials,
        store=cast("SessionStore", None),
        state=state,
        update_settings=lambda settings: setattr(state, "settings", settings),
        outbox=cast("Outbox", None),
        terminal=cast("Terminal", None),
    )
    return ProviderMenu(context)


def _openai_provider(oauth: _BrowserLogin | None) -> Provider:
    """OpenAI with an API key, and with the browser login ``oauth`` if given."""
    connections = [
        Connection(
            id="api-key",
            provider="openai",
            api=OpenAIResponsesAPI,
            base_url="https://api.openai.com/v1",
            label="OpenAI API key",
        )
    ]
    if oauth is not None:
        connections.append(
            Connection(
                id="oauth",
                provider="openai",
                api=OpenAICodexResponsesAPI,
                base_url="https://chatgpt.com/backend-api/codex",
                label="ChatGPT Plus/Pro",
                oauth=oauth,
            )
        )
    return Provider(id="openai", name="OpenAI", connections=tuple(connections))


async def _finish(menu: ProviderMenu) -> None:
    """Let the login run until it ends."""
    if (login := menu._login) is not None:
        await asyncio.wait([login])


@pytest.fixture
def credentials() -> _Credentials:
    return _Credentials()


def test_providers_with_a_connection_are_marked(
    overlays: Overlays, credentials: _Credentials, state: AppState
) -> None:
    credentials["openai:api-key"] = ApiKeyCredential(type="api_key", value="k")
    _menu(overlays, credentials, state).open()
    assert [item.marker for item in overlays.top.items] == ["✓"]


def test_several_connections_are_offered_in_a_picker(
    overlays: Overlays, credentials: _Credentials, state: AppState
) -> None:
    credentials["openai:oauth"] = _credential()
    _menu(overlays, credentials, state).select(_openai_provider(_BrowserLogin()))

    assert (type(overlays.top), overlays.top.title) == (Picker, "OpenAI")
    assert [(item.label, item.marker) for item in overlays.top.items] == [
        ("OpenAI API key", None),
        ("ChatGPT Plus/Pro", "✓"),
    ]


def test_an_api_key_is_stored_and_picks_a_model(
    overlays: Overlays, credentials: _Credentials, state: AppState
) -> None:
    _menu(overlays, credentials, state).select(_openai_provider(_BrowserLogin()))
    overlays.pick("OpenAI API key")

    dialog = overlays.top
    assert (type(dialog), dialog.title, dialog.masked) == (
        InputDialog,
        "Enter OpenAI API key",
        True,
    )
    dialog.submit("secret")

    assert credentials["openai:api-key"] == ApiKeyCredential(type="api_key", value="secret")
    assert state.settings.agent_settings.model == "gpt-5.5"
    assert overlays.stack == []


def test_a_single_connection_skips_the_picker(
    overlays: Overlays, credentials: _Credentials, state: AppState
) -> None:
    _menu(overlays, credentials, state).select(_openai_provider(None))
    assert overlays.kinds == [InputDialog]


async def test_a_browser_login_stores_the_credential(
    overlays: Overlays, credentials: _Credentials, state: AppState, opened_urls: list[str]
) -> None:
    menu = _menu(overlays, credentials, state)
    menu.select(_openai_provider(_BrowserLogin()))
    overlays.pick("ChatGPT Plus/Pro")
    await _finish(menu)

    assert opened_urls == ["https://auth.example"]
    assert credentials["openai:oauth"] == _credential()
    assert state.settings.agent_settings.model == "gpt-5.5"
    assert overlays.stack == []


@pytest.mark.usefixtures("opened_urls")
async def test_a_login_can_be_finished_by_pasting_into_the_prompt(
    overlays: Overlays, credentials: _Credentials, state: AppState
) -> None:
    login = _PromptedLogin()
    menu = _menu(overlays, credentials, state)
    menu.select(_openai_provider(login))
    overlays.pick("ChatGPT Plus/Pro")
    await asyncio.sleep(0)

    dialog = overlays.top
    assert (type(dialog), dialog.title, dialog.detail) == (
        InputDialog,
        strings.Palette.Providers.connecting("OpenAI", "ChatGPT Plus/Pro"),
        "Paste the callback URL",
    )
    dialog.submit("https://callback.example")
    await _finish(menu)

    assert login.answer == "https://callback.example"
    assert credentials["openai:oauth"] == _credential()


@pytest.mark.usefixtures("opened_urls")
async def test_closing_the_prompt_cancels_the_login(
    overlays: Overlays, credentials: _Credentials, state: AppState
) -> None:
    menu = _menu(overlays, credentials, state)
    menu.select(_openai_provider(_PromptedLogin()))
    overlays.pick("ChatGPT Plus/Pro")
    await asyncio.sleep(0)
    login = menu._login
    assert login is not None

    overlays.top.cancel()
    await asyncio.wait([login])

    assert login.cancelled()
    assert overlays.kinds == [Picker]  # Back to choosing how to connect.
    assert credentials == {}
    assert menu._login is None


@pytest.mark.usefixtures("opened_urls")
async def test_a_new_login_replaces_one_under_way(
    overlays: Overlays, credentials: _Credentials, state: AppState
) -> None:
    menu = _menu(overlays, credentials, state)
    menu.select(_openai_provider(_PromptedLogin()))
    overlays.pick("ChatGPT Plus/Pro")
    await asyncio.sleep(0)
    first = menu._login
    assert first is not None

    overlays.pick("ChatGPT Plus/Pro", overlays.stack[0])
    await asyncio.wait([first])
    await asyncio.sleep(0)

    assert first.cancelled()
    assert menu._login is not None
    assert overlays.top.title == strings.Palette.Providers.connecting("OpenAI", "ChatGPT Plus/Pro")


async def test_a_failed_login_says_why(
    overlays: Overlays, credentials: _Credentials, state: AppState
) -> None:
    menu = _menu(overlays, credentials, state)
    menu.select(_openai_provider(_FailingLogin()))
    overlays.pick("ChatGPT Plus/Pro")
    await _finish(menu)

    dialog = overlays.top
    assert (dialog.title, dialog.detail) == ("Provider login failed", "token exchange failed")
    assert overlays.kinds == [MessageDialog]
