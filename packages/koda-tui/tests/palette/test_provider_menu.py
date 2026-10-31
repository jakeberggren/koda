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
    from koda_tui.settings import AppSettings
    from koda_tui.state import AppState
    from koda_tui.ui.overlays import Overlays
    from koda_tui.ui.widgets import DialogChoice


class _FakeCoreSettings:
    credential_mode = "local"
    model: str | None = None
    thinking = "medium"

    def __init__(self) -> None:
        self.credentials: dict[str, ProviderCredential] = {}

    def set_credential(self, provider: str, credential: ProviderCredential) -> None:
        self.credentials[provider] = credential

    def update(self, **changes: object) -> None:
        for key, value in changes.items():
            setattr(self, key, value)


class _FakeAppSettings:
    def __init__(self) -> None:
        self.core = _FakeCoreSettings()


class _FakeService:
    def list_configured_providers(self) -> list[ProviderDefinition]:
        return []

    def list_providers(self) -> list[ProviderDefinition]:
        return []

    def list_models(self, provider: str) -> list[ModelDefinition]:
        _ = provider
        return [ModelDefinition(id="gpt-5.5", name="gpt-5.5", provider="openai")]


class _FakeOverlays:
    """Records what the menu opens: the dialogs are replaced by records of their arguments."""

    def __init__(self) -> None:
        self.service = _FakeService()
        self.settings = _FakeAppSettings()
        self.text_dialogs: list[dict[str, object]] = []
        self.palettes: list[dict[str, object]] = []
        self.choices: list[dict[str, object]] = []
        self.closed = False

    def open(self, overlay: tuple[str, dict[str, object]]) -> None:
        kind, fields = overlay
        {"text": self.text_dialogs, "picker": self.palettes, "choice": self.choices}[kind].append(
            fields,
        )

    def close(self) -> None:
        pass

    def close_all(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _record_dialogs(monkeypatch: pytest.MonkeyPatch) -> None:
    def text(
        *,
        title: str,
        on_submit: object,
        detail: str | None = None,
        mask_input: bool = False,
        **_: object,
    ) -> tuple:
        return (
            "text",
            {"title": title, "detail": detail, "on_submit": on_submit, "mask_input": mask_input},
        )

    def choice(message: str, choices: list[DialogChoice], **_: object) -> tuple:
        return ("choice", {"message": message, "choices": choices})

    def picker(title: str, items: list[object], **fields: object) -> tuple:
        return ("picker", {"title": title, "items": items, **fields})

    monkeypatch.setattr(providers, "InputDialog", text)
    monkeypatch.setattr(providers, "ChoiceDialog", choice)
    monkeypatch.setattr(providers, "Picker", picker)


class _FakeAuthProvider:
    id = "openai:oauth"

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
        callbacks.on_auth_url("https://auth.example")
        return OAuthCredential(
            type="oauth",
            access_token="access-token",  # noqa: S106
            refresh_token="refresh-token",  # noqa: S106
            expires_at="123",
            metadata={"chatgpt_account_id": "account-id"},
        )

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        return credential


def _provider_menu(
    palette: _FakeOverlays,
    auth_registry: ProviderAuthRegistry | None = None,
) -> ProviderMenu:
    context = PaletteContext(
        overlays=cast("Overlays", palette),
        service=cast("KodaService", palette.service),
        settings=cast("AppSettings", palette.settings),
        state=cast("AppState", None),
        cancel_streaming=lambda: None,
        refresh_theme=lambda: None,
    )
    return ProviderMenu(
        context,
        auth_registry or ProviderAuthRegistry({"openai:oauth": _FakeAuthProvider()}),
    )


def _openai_provider() -> ProviderDefinition:
    return ProviderDefinition(
        id="openai",
        name="OpenAI",
        connections=[
            ProviderConnectionDefinition(
                id="api-key",
                label="OpenAI API key",
                auth="api-key",
            ),
            ProviderConnectionDefinition(
                id="oauth",
                label="ChatGPT Plus/Pro",
                auth="oauth",
            ),
        ],
    )


def _last_choices(palette: _FakeOverlays) -> list[DialogChoice]:
    return cast("list[DialogChoice]", palette.choices[-1]["choices"])


def test_provider_menu_provider_opens_connection_choice() -> None:
    palette = _FakeOverlays()
    menu = _provider_menu(palette)

    menu.select(_openai_provider())

    assert palette.choices[0]["message"] == "Connect OpenAI using:"
    assert [choice.label for choice in _last_choices(palette)] == [
        "ChatGPT Plus/Pro",
        "OpenAI API key",
    ]


def test_provider_menu_api_key_connection_opens_key_dialog() -> None:
    palette = _FakeOverlays()
    menu = _provider_menu(palette)
    provider = _openai_provider()

    menu.select(provider)
    _last_choices(palette)[1].on_select()

    assert palette.text_dialogs == [
        {
            "title": "Enter OpenAI API key",
            "detail": None,
            "on_submit": palette.text_dialogs[0]["on_submit"],
            "mask_input": True,
        }
    ]

    on_submit = cast("Callable[[str], None]", palette.text_dialogs[0]["on_submit"])
    on_submit("api-key")

    credential = palette.settings.core.credentials["openai:api-key"]
    assert isinstance(credential, ApiKeyCredential)
    assert credential.value == "api-key"


async def test_provider_menu_oauth_connection_stores_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened_urls: list[str] = []
    palette = _FakeOverlays()
    menu = _provider_menu(palette)
    monkeypatch.setattr("webbrowser.open", opened_urls.append)
    provider = _openai_provider()

    menu.select(provider)
    _last_choices(palette)[0].on_select()

    await next(iter(menu._oauth_tasks))  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]

    credential = palette.settings.core.credentials["openai:oauth"]
    assert isinstance(credential, OAuthCredential)
    assert opened_urls == ["https://auth.example"]
    assert credential.metadata["chatgpt_account_id"] == "account-id"
    assert palette.settings.core.model == "gpt-5.5"
    assert palette.closed is True


async def test_provider_menu_oauth_prompt_uses_text_dialog() -> None:
    palette = _FakeOverlays()
    menu = _provider_menu(palette)

    task = asyncio.create_task(
        menu._prompt_oauth_code("Paste callback URL")  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    )
    await asyncio.sleep(0)

    assert palette.text_dialogs == [
        {
            "title": "Complete browser login",
            "detail": "Paste callback URL",
            "on_submit": palette.text_dialogs[0]["on_submit"],
            "mask_input": False,
        }
    ]

    on_submit = cast("Callable[[str], None]", palette.text_dialogs[0]["on_submit"])
    on_submit("callback-url")

    assert await task == "callback-url"


def test_provider_menu_oauth_progress_uses_text_dialog() -> None:
    palette = _FakeOverlays()
    menu = _provider_menu(palette)

    menu._show_oauth_progress("Enter code ABCD-EFGH")  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]

    assert palette.text_dialogs == [
        {
            "title": "Enter code ABCD-EFGH",
            "detail": None,
            "on_submit": palette.text_dialogs[0]["on_submit"],
            "mask_input": False,
        }
    ]
