"""Provider palette items and actions."""

from __future__ import annotations

import asyncio
import webbrowser
from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda.llm.auth.protocols import OAuthLoginCallbacks
from koda_common.logging import get_logger
from koda_common.settings.credentials import ApiKeyCredential
from koda_tui import strings
from koda_tui.appearance import Tokens
from koda_tui.ui.widgets import InputDialog, ListItem, MessageDialog, Picker

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda.llm import ProviderConnectionDefinition, ProviderDefinition
    from koda.llm.auth.registry import ProviderAuthRegistry
    from koda_common.settings.credentials import ProviderCredential
    from koda_tui.palette.context import PaletteContext


log = get_logger(__name__)

_CONNECTED = "✓"

_PROXY_MANAGED_PROVIDER_FOOTER: StyleAndTextTuples = [
    (Tokens.Text.WARNING, strings.Palette.Providers.PROXY_MANAGED)
]


@dataclass(frozen=True, slots=True)
class ProviderConnectionSelection:
    """One way to connect a provider, such as an API key or a browser login."""

    provider: ProviderDefinition
    connection: ProviderConnectionDefinition

    @property
    def credential_key(self) -> str:
        return f"{self.provider.id}:{self.connection.id}"

    @property
    def label(self) -> str:
        return self.connection.label or self.connection.id


class ProviderMenu:
    """Connects providers: pick one, pick how if it has several ways, then enter an API
    key or log in through the browser. With proxy-managed credentials, providers are
    only listed; they are connected outside Koda.

    A browser login runs in the background, one at a time; closing its dialog cancels it.
    """

    def __init__(self, context: PaletteContext, auth_registry: ProviderAuthRegistry) -> None:
        self._overlays = context.overlays
        self._service = context.service
        self._settings = context.settings
        self._auth_registry = auth_registry
        self._login: asyncio.Task[None] | None = None

    def open(self) -> None:
        """Open the provider list."""
        proxy_managed = self._settings.proxy_managed
        self._overlays.open(
            Picker(
                strings.Palette.Providers.TITLE,
                self._provider_items(proxy_managed=proxy_managed),
                on_select=lambda item: self.select(item.data),
                heading=(
                    strings.Palette.Providers.PROXY_MANAGED_HEADING
                    if proxy_managed
                    else strings.Palette.Providers.HEADING
                ),
                footer=_PROXY_MANAGED_PROVIDER_FOOTER if proxy_managed else None,
                on_close=self._overlays.close,
            ),
        )

    def select(self, provider: ProviderDefinition) -> None:
        """Connect ``provider``: pick how, if it has several ways."""
        if self._settings.proxy_managed:
            self._overlays.close_all()
            return
        connections = [ProviderConnectionSelection(provider, c) for c in provider.connections]
        if len(connections) == 1:
            self._connect(connections[0])
            return
        self._overlays.open(
            Picker(
                provider.name,
                [
                    ListItem(
                        label=selection.label,
                        detail=selection.connection.description or "",
                        marker=_CONNECTED if self._connected(selection) else None,
                        data=selection,
                    )
                    for selection in connections
                ],
                on_select=lambda item: self._connect(item.data),
                heading=strings.Palette.Providers.CONNECTIONS_HEADING,
                on_close=self._overlays.close,
            ),
        )

    def _provider_items(self, *, proxy_managed: bool) -> list[ListItem[ProviderDefinition]]:
        """The providers, those with a connection marked, unless credentials are managed
        outside Koda."""
        return [
            ListItem(
                label=provider.name,
                detail=provider.description or "",
                marker=_CONNECTED if not proxy_managed and self._any_connected(provider) else None,
                data=provider,
            )
            for provider in self._service.list_providers()
        ]

    def _any_connected(self, provider: ProviderDefinition) -> bool:
        return any(
            self._connected(ProviderConnectionSelection(provider, connection))
            for connection in provider.connections
        )

    def _connected(self, selection: ProviderConnectionSelection) -> bool:
        return bool(self._settings.core.get_credential(selection.credential_key))

    def _connect(self, selection: ProviderConnectionSelection) -> None:
        """Log in through the browser, or ask for the API key."""
        if selection.connection.auth == "oauth":
            self._start_login(selection)
            return
        self._overlays.open(
            InputDialog(
                title=strings.Palette.Providers.enter(selection.label),
                mask_input=True,
                on_submit=lambda key: self._save(
                    selection, ApiKeyCredential(type="api_key", value=key)
                ),
                on_cancel=self._overlays.close,
            ),
        )

    def _save(self, selection: ProviderConnectionSelection, credential: ProviderCredential) -> None:
        """Store the credential, pick the provider's first model if none is picked yet,
        and close the palette."""
        self._settings.core.set_credential(selection.credential_key, credential)
        if self._settings.core.model is None and (
            models := self._service.list_models(selection.provider.id)
        ):
            self._settings.core.update(provider=models[0].provider, model=models[0].id)
        self._overlays.close_all()

    def _start_login(self, selection: ProviderConnectionSelection) -> None:
        """Log in through the browser in the background, replacing any login under way."""
        if self._login is not None:
            self._login.cancel()
        self._login = asyncio.create_task(self._log_in(selection))
        self._login.add_done_callback(self._on_login_done)

    async def _log_in(self, selection: ProviderConnectionSelection) -> None:
        title = strings.Palette.Providers.connecting(selection.provider.name, selection.label)
        credential = await self._auth_registry.get(selection.credential_key).login(
            OAuthLoginCallbacks(
                on_auth_url=_open_in_browser,
                on_prompt=lambda message: self._ask(title, message),
            )
        )
        self._save(selection, credential)

    async def _ask(self, title: str, message: str) -> str:
        """Ask for what the login prompts for, such as the callback URL. The login can
        also finish in the browser first, which cancels the question."""
        answer: asyncio.Future[str] = asyncio.get_running_loop().create_future()

        def submit(value: str) -> None:
            if not answer.done():
                answer.set_result(value)

        self._overlays.open(
            InputDialog(title=title, detail=message, on_submit=submit, on_cancel=self._abandon)
        )
        return await answer

    def _abandon(self) -> None:
        """Close the login's dialog and cancel the login."""
        self._overlays.close()
        if self._login is not None:
            self._login.cancel()

    def _on_login_done(self, task: asyncio.Task[None]) -> None:
        """Show why the login failed, if it did; a cancelled login just ends."""
        if task is not self._login:
            return  # Replaced by a newer login.
        self._login = None
        if task.cancelled() or (error := task.exception()) is None:
            return
        log.warning("provider_oauth_login_failed", error=repr(error))
        self._overlays.close_all()
        self._overlays.open(
            MessageDialog(
                title=strings.Palette.Providers.LOGIN_FAILED,
                detail=str(error),
                on_close=self._overlays.close,
            ),
        )


def _open_in_browser(url: str) -> None:
    webbrowser.open(url)
