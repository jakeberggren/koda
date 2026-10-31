"""Tests for the provider menu: picking how to connect, API keys, and browser logins."""

# ruff: noqa: SLF001 - the login task is private

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import pytest

from koda.llm import ModelDefinition, ProviderConnectionDefinition, ProviderDefinition
from koda.llm.auth.registry import ProviderAuthRegistry
from koda_common.settings.credentials import ApiKeyCredential, OAuthCredential, ProviderCredential
from koda_tui.palette.context import PaletteContext
from koda_tui.palette.menus import providers
from koda_tui.palette.menus.providers import ProviderMenu

if TYPE_CHECKING:
    from collections.abc import Callable

    from koda.llm.auth.protocols import OAuthLoginCallbacks
    from koda_service import KodaService
    from koda_tui.messaging import Conversation, Outbox
    from koda_tui.settings import AppSettings
    from koda_tui.state import AppState
    from koda_tui.terminal import Terminal
    from koda_tui.ui.overlays import Overlays
    from koda_tui.ui.primitives import ListItem


class _FakeCoreSettings:
    model: str | None = None

    def __init__(self) -> None:
        self.credentials: dict[str, ProviderCredential] = {}

    def get_credential(self, key: str) -> ProviderCredential | None:
        return self.credentials.get(key)

    def set_credential(self, key: str, credential: ProviderCredential) -> None:
        self.credentials[key] = credential

    def update(self, **changes: object) -> None:
        for key, value in changes.items():
            setattr(self, key, value)


class _FakeAppSettings:
    def __init__(self) -> None:
        self.core = _FakeCoreSettings()
        self.proxy_managed = False


class _FakeService:
    def list_providers(self) -> list[ProviderDefinition]:
        return [_openai_provider()]

    def list_models(self, provider: str) -> list[ModelDefinition]:
        _ = provider
        return [ModelDefinition(id="gpt-5.5", name="gpt-5.5", provider="openai")]


class _FakeOverlays:
    """A stack of records of what the menu opens: each dialog is replaced by its kind
    and arguments."""

    def __init__(self) -> None:
        self.stack: list[tuple[str, dict]] = []

    def open(self, overlay: tuple[str, dict]) -> None:
        self.stack.append(overlay)

    def close(self) -> None:
        self.stack.pop()

    def close_all(self) -> None:
        self.stack.clear()

    @property
    def top(self) -> tuple[str, dict]:
        return self.stack[-1]

    @property
    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.stack]


@pytest.fixture(autouse=True)
def _record_dialogs(monkeypatch: pytest.MonkeyPatch) -> None:
    def record(kind: str) -> Callable[..., tuple[str, dict]]:
        return lambda *args, **fields: (kind, {"args": args, **fields})

    monkeypatch.setattr(providers, "InputDialog", record("input"))
    monkeypatch.setattr(providers, "MessageDialog", record("message"))
    monkeypatch.setattr(providers, "Picker", record("picker"))


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


def _menu(
    overlays: _FakeOverlays, settings: _FakeAppSettings, login: _BrowserLogin
) -> ProviderMenu:
    context = PaletteContext(
        overlays=cast("Overlays", overlays),
        service=cast("KodaService", _FakeService()),
        settings=cast("AppSettings", settings),
        state=cast("AppState", None),
        conversation=cast("Conversation", None),
        outbox=cast("Outbox", None),
        terminal=cast("Terminal", None),
    )
    return ProviderMenu(context, ProviderAuthRegistry({"openai:oauth": login}))


def _openai_provider(*, oauth: bool = True) -> ProviderDefinition:
    connections = [ProviderConnectionDefinition(id="api-key", label="OpenAI API key")]
    if oauth:
        connections.append(
            ProviderConnectionDefinition(id="oauth", label="ChatGPT Plus/Pro", auth="oauth")
        )
    return ProviderDefinition(id="openai", name="OpenAI", connections=connections)


def _items(overlay: tuple[str, dict]) -> list[ListItem]:
    return overlay[1]["args"][1]


def _pick(overlay: tuple[str, dict], label: str) -> None:
    item = next(item for item in _items(overlay) if item.label == label)
    overlay[1]["on_select"](item)


async def _finish(menu: ProviderMenu) -> None:
    """Let the login run until it ends."""
    if (login := menu._login) is not None:
        await asyncio.wait([login])


@pytest.fixture
def overlays() -> _FakeOverlays:
    return _FakeOverlays()


@pytest.fixture
def settings() -> _FakeAppSettings:
    return _FakeAppSettings()


def test_providers_with_a_connection_are_marked(
    overlays: _FakeOverlays, settings: _FakeAppSettings
) -> None:
    settings.core.credentials["openai:api-key"] = ApiKeyCredential(type="api_key", value="k")
    _menu(overlays, settings, _BrowserLogin()).open()
    assert [item.marker for item in _items(overlays.top)] == ["✓"]


def test_several_connections_are_offered_in_a_picker(
    overlays: _FakeOverlays, settings: _FakeAppSettings
) -> None:
    settings.core.credentials["openai:oauth"] = _credential()
    _menu(overlays, settings, _BrowserLogin()).select(_openai_provider())

    kind, fields = overlays.top
    assert (kind, fields["args"][0]) == ("picker", "OpenAI")
    assert [(item.label, item.marker) for item in _items(overlays.top)] == [
        ("OpenAI API key", None),
        ("ChatGPT Plus/Pro", "✓"),
    ]


def test_an_api_key_is_stored_and_picks_a_model(
    overlays: _FakeOverlays, settings: _FakeAppSettings
) -> None:
    _menu(overlays, settings, _BrowserLogin()).select(_openai_provider())
    _pick(overlays.top, "OpenAI API key")

    kind, fields = overlays.top
    assert (kind, fields["title"], fields["mask_input"]) == ("input", "Enter OpenAI API key", True)
    fields["on_submit"]("secret")

    assert settings.core.credentials["openai:api-key"] == ApiKeyCredential(
        type="api_key", value="secret"
    )
    assert settings.core.model == "gpt-5.5"
    assert overlays.stack == []


def test_a_single_connection_skips_the_picker(
    overlays: _FakeOverlays, settings: _FakeAppSettings
) -> None:
    _menu(overlays, settings, _BrowserLogin()).select(_openai_provider(oauth=False))
    assert overlays.kinds == ["input"]


def test_proxy_managed_providers_only_close_the_palette(
    overlays: _FakeOverlays, settings: _FakeAppSettings
) -> None:
    settings.proxy_managed = True
    overlays.open(("picker", {}))
    _menu(overlays, settings, _BrowserLogin()).select(_openai_provider())
    assert overlays.stack == []


async def test_a_browser_login_stores_the_credential(
    overlays: _FakeOverlays, settings: _FakeAppSettings, opened_urls: list[str]
) -> None:
    menu = _menu(overlays, settings, _BrowserLogin())
    menu.select(_openai_provider())
    _pick(overlays.top, "ChatGPT Plus/Pro")
    await _finish(menu)

    assert opened_urls == ["https://auth.example"]
    assert settings.core.credentials["openai:oauth"] == _credential()
    assert settings.core.model == "gpt-5.5"
    assert overlays.stack == []


@pytest.mark.usefixtures("opened_urls")
async def test_a_login_can_be_finished_by_pasting_into_the_prompt(
    overlays: _FakeOverlays, settings: _FakeAppSettings
) -> None:
    login = _PromptedLogin()
    menu = _menu(overlays, settings, login)
    menu.select(_openai_provider())
    _pick(overlays.top, "ChatGPT Plus/Pro")
    await asyncio.sleep(0)

    kind, fields = overlays.top
    assert (kind, fields["title"], fields["detail"]) == (
        "input",
        "Connecting OpenAI ChatGPT Plus/Pro",
        "Paste the callback URL",
    )
    fields["on_submit"]("https://callback.example")
    await _finish(menu)

    assert login.answer == "https://callback.example"
    assert settings.core.credentials["openai:oauth"] == _credential()


@pytest.mark.usefixtures("opened_urls")
async def test_closing_the_prompt_cancels_the_login(
    overlays: _FakeOverlays, settings: _FakeAppSettings
) -> None:
    menu = _menu(overlays, settings, _PromptedLogin())
    menu.select(_openai_provider())
    _pick(overlays.top, "ChatGPT Plus/Pro")
    await asyncio.sleep(0)
    login = menu._login
    assert login is not None

    overlays.top[1]["on_cancel"]()
    await asyncio.wait([login])

    assert login.cancelled()
    assert overlays.kinds == ["picker"]  # Back to choosing how to connect.
    assert settings.core.credentials == {}
    assert menu._login is None


@pytest.mark.usefixtures("opened_urls")
async def test_a_new_login_replaces_one_under_way(
    overlays: _FakeOverlays, settings: _FakeAppSettings
) -> None:
    menu = _menu(overlays, settings, _PromptedLogin())
    menu.select(_openai_provider())
    _pick(overlays.top, "ChatGPT Plus/Pro")
    await asyncio.sleep(0)
    first = menu._login
    assert first is not None

    _pick(overlays.stack[0], "ChatGPT Plus/Pro")
    await asyncio.wait([first])
    await asyncio.sleep(0)

    assert first.cancelled()
    assert menu._login is not None
    assert overlays.top[1]["title"] == "Connecting OpenAI ChatGPT Plus/Pro"


async def test_a_failed_login_says_why(overlays: _FakeOverlays, settings: _FakeAppSettings) -> None:
    menu = _menu(overlays, settings, _FailingLogin())
    menu.select(_openai_provider())
    _pick(overlays.top, "ChatGPT Plus/Pro")
    await _finish(menu)

    kind, fields = overlays.top
    assert (kind, fields["title"], fields["detail"]) == (
        "message",
        "Provider login failed",
        "token exchange failed",
    )
    assert overlays.kinds == ["message"]
