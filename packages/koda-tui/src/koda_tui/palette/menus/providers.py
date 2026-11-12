"""Provider palette items and actions."""

from __future__ import annotations

import asyncio
import webbrowser
from copy import replace
from dataclasses import dataclass
from typing import TYPE_CHECKING

from structlog import get_logger

from koda import llm
from koda_tui import strings
from koda_tui.appearance import Icons
from koda_tui.ui.widgets import InputDialog, ListItem, MessageDialog, Picker

if TYPE_CHECKING:
    from koda.llm import Connection, Provider, ProviderCredential
    from koda_tui.palette.context import PaletteContext


log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderConnectionSelection:
    """One way to connect a provider, such as an API key or a browser login."""

    provider: Provider
    connection: Connection

    @property
    def credential_key(self) -> str:
        return self.connection.credential_key

    @property
    def label(self) -> str:
        return self.connection.label or self.connection.id


class ProviderMenu:
    """Connects providers: pick one, pick how if it has several ways, then enter an API
    key or log in through the browser.

    A browser login runs in the background, one at a time; closing its dialog cancels it.
    """

    def __init__(self, context: PaletteContext) -> None:
        self._overlays = context.overlays
        self._catalog = context.catalog
        self._context = context
        self._login: asyncio.Task[None] | None = None

    def open(self) -> None:
        """Open the provider list."""
        self._overlays.open(
            Picker(
                strings.Palette.Providers.TITLE,
                self._provider_items(),
                on_select=lambda item: self.select(item.data),
                heading=strings.Palette.Providers.HEADING,
                on_close=self._overlays.close,
            ),
        )

    def select(self, provider: Provider) -> None:
        """Connect ``provider``: pick how, if it has several ways."""
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
                        marker=Icons.DONE if self._connected(selection) else None,
                        data=selection,
                    )
                    for selection in connections
                ],
                on_select=lambda item: self._connect(item.data),
                heading=strings.Palette.Providers.CONNECTIONS_HEADING,
                on_close=self._overlays.close,
            ),
        )

    def _provider_items(self) -> list[ListItem[Provider]]:
        """The providers, those with a connection marked."""
        return [
            ListItem(
                label=provider.name,
                detail=provider.description or "",
                marker=Icons.DONE if self._any_connected(provider) else None,
                data=provider,
            )
            for provider in self._catalog.providers()
        ]

    def _any_connected(self, provider: Provider) -> bool:
        return any(
            self._connected(ProviderConnectionSelection(provider, connection))
            for connection in provider.connections
        )

    def _connected(self, selection: ProviderConnectionSelection) -> bool:
        return bool(self._context.credentials.get_credential(selection.credential_key))

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
                    selection, llm.ApiKeyCredential(type="api_key", value=key)
                ),
                on_cancel=self._overlays.close,
            ),
        )

    def _save(self, selection: ProviderConnectionSelection, credential: ProviderCredential) -> None:
        """Store the credential, pick the provider's first model if none is picked yet,
        and close the palette."""
        self._context.credentials.set_credential(selection.credential_key, credential)
        settings = self._context.settings
        if settings.model is None and (models := self._catalog.models(selection.provider.id)):
            settings = replace(settings, provider=models[0].provider, model=models[0].id)
        self._context.update_settings(settings)
        self._overlays.close_all()

    def _start_login(self, selection: ProviderConnectionSelection) -> None:
        """Log in through the browser in the background, replacing any login under way."""
        if self._login is not None:
            self._login.cancel()
        self._login = asyncio.create_task(self._log_in(selection))
        self._login.add_done_callback(self._on_login_done)

    async def _log_in(self, selection: ProviderConnectionSelection) -> None:
        title = strings.Palette.Providers.connecting(selection.provider.name, selection.label)
        credential = await llm.login(
            selection.connection,
            llm.OAuthLoginCallbacks(
                on_auth_url=_open_in_browser,
                on_prompt=lambda message: self._ask(title, message),
            ),
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
