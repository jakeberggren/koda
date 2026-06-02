"""Provider palette items and actions."""

from __future__ import annotations

import asyncio
import webbrowser
from dataclasses import dataclass
from typing import TYPE_CHECKING

from koda.llm.auth.protocols import OAuthLoginCallbacks
from koda_common.logging import get_logger
from koda_common.settings.credentials import ApiKeyCredential
from koda_tui.overlays.dialogs import DialogChoice
from koda_tui.palette.items import ListItem
from koda_tui.palette.menus.models import apply_model_selection

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda.llm import ProviderConnectionDefinition, ProviderDefinition
    from koda.llm.auth.registry import ProviderAuthRegistry
    from koda_tui.palette.palette import Palette


log = get_logger(__name__)

_TITLE = "Connect Provider"
_LIST_HEADING = "Configure LLM Provider API Key"
_PROXY_MANAGED_LIST_HEADING = "Available Providers"

_PROXY_MANAGED_PROVIDER_FOOTER: StyleAndTextTuples = [
    (
        "fg:ansiyellow",
        "Proxy-managed credentials: use sbx secret set outside Koda; "
        "connectivity is verified on request.",
    )
]


@dataclass(frozen=True, slots=True)
class ProviderConnectionSelection:
    provider: ProviderDefinition
    connection: ProviderConnectionDefinition

    @property
    def credential_key(self) -> str:
        return f"{self.provider.id}:{self.connection.id}"

    @property
    def label(self) -> str:
        return self.connection.label or self.connection.id


class ProviderMenu:
    """Provider submenu behavior."""

    def __init__(self, palette: Palette, auth_registry: ProviderAuthRegistry) -> None:
        self._palette = palette
        self._service = palette.service
        self._settings = palette.app_settings
        self._auth_registry = auth_registry
        self._oauth_tasks: set[asyncio.Task[None]] = set()

    def _is_proxy_managed(self) -> bool:
        return self._settings.core.credential_mode == "proxy-managed"

    @staticmethod
    def _connection_key(provider: ProviderDefinition, connection_id: str) -> str:
        return f"{provider.id}:{connection_id}"

    def _connected_connection_keys(self) -> set[str]:
        return {
            self._connection_key(provider, connection.id)
            for provider in self._service.list_providers()
            for connection in provider.connections
            if self._settings.core.get_credential(self._connection_key(provider, connection.id))
        }

    def _items(self, *, proxy_managed: bool) -> list[ListItem]:
        """Build provider selection items."""
        connected = self._connected_connection_keys()
        return [
            ListItem(
                id=f"select_provider:{provider.id}",
                label=provider.name,
                detail=provider.description or "",
                marker=(
                    "✓"
                    if not proxy_managed
                    and any(
                        self._connection_key(provider, connection.id) in connected
                        for connection in provider.connections
                    )
                    else None
                ),
                data=provider,
            )
            for provider in self._service.list_providers()
        ]

    def open(self) -> None:
        """Open the provider selection submenu."""
        proxy_managed = self._is_proxy_managed()
        list_heading = _PROXY_MANAGED_LIST_HEADING if proxy_managed else _LIST_HEADING
        footer = _PROXY_MANAGED_PROVIDER_FOOTER if proxy_managed else None
        self._palette.open_palette(
            self._items(proxy_managed=proxy_managed),
            title=_TITLE,
            list_heading=list_heading,
            footer=footer,
        )

    def _auto_select_first_model(self, provider: ProviderDefinition) -> None:
        if self._settings.core.model is not None:
            return
        models = self._service.list_models(provider.id)
        if models:
            apply_model_selection(models[0], current_model=None, settings=self._settings.core)

    def _submit_api_key(self, selection: ProviderConnectionSelection, key: str) -> None:
        self._settings.core.set_credential(
            selection.credential_key,
            ApiKeyCredential(type="api_key", value=key),
        )
        self._auto_select_first_model(selection.provider)
        self._palette.close_all_overlays()

    async def _connect_oauth_provider(self, selection: ProviderConnectionSelection) -> None:
        auth_provider = self._auth_registry.get(selection.credential_key)
        self._show_oauth_progress(f"Connecting {selection.provider.name} {selection.label}...")
        credential = await auth_provider.login(
            OAuthLoginCallbacks(
                on_auth_url=self._open_auth_url,
                on_prompt=self._prompt_oauth_code,
            )
        )
        self._settings.core.set_credential(selection.credential_key, credential)
        self._auto_select_first_model(selection.provider)
        self._palette.close_all_overlays()

    @staticmethod
    def _open_auth_url(url: str) -> None:
        webbrowser.open(url)

    async def _prompt_oauth_code(self, message: str) -> str:
        loop = asyncio.get_running_loop()
        result: asyncio.Future[str] = loop.create_future()

        def submit(value: str) -> None:
            if not result.done():
                result.set_result(value)

        self._palette.open_text_dialog(
            title="Complete browser login",
            detail=message,
            on_submit=submit,
        )
        return await result

    def _show_oauth_progress(self, message: str) -> None:
        self._palette.open_text_dialog(
            title=message,
            on_submit=lambda _: None,
        )

    def _on_oauth_task_done(self, task: asyncio.Task[None]) -> None:
        self._oauth_tasks.discard(task)
        try:
            task.result()
        except Exception as error:
            log.warning("provider_oauth_login_failed", error=repr(error))
            self._palette.open_message(
                title="Provider login failed",
                detail=str(error),
            )

    def _select_oauth_provider(self, selection: ProviderConnectionSelection) -> None:
        task = asyncio.create_task(self._connect_oauth_provider(selection))
        self._oauth_tasks.add(task)
        task.add_done_callback(self._on_oauth_task_done)

    def _connection_items(
        self,
        provider: ProviderDefinition,
        *,
        proxy_managed: bool,
    ) -> list[ListItem]:
        connected = self._connected_connection_keys()
        return [
            ListItem(
                id=f"select_provider_connection:{provider.id}:{connection.id}",
                label=connection.label or connection.id,
                detail=connection.description or "",
                marker=(
                    "✓"
                    if not proxy_managed
                    and self._connection_key(provider, connection.id) in connected
                    else None
                ),
                data=ProviderConnectionSelection(provider=provider, connection=connection),
            )
            for connection in provider.connections
        ]

    def _open_provider_connections(self, provider: ProviderDefinition) -> None:
        api_key_selection = next(
            (
                ProviderConnectionSelection(provider=provider, connection=connection)
                for connection in provider.connections
                if connection.auth == "api-key"
            ),
            None,
        )
        oauth_selection = next(
            (
                ProviderConnectionSelection(provider=provider, connection=connection)
                for connection in provider.connections
                if connection.auth == "oauth"
            ),
            None,
        )
        if api_key_selection is None or oauth_selection is None:
            if len(provider.connections) == 1:
                self._select_connection(
                    ProviderConnectionSelection(
                        provider=provider,
                        connection=provider.connections[0],
                    )
                )
            else:
                self._palette.open_palette(
                    self._connection_items(provider, proxy_managed=self._is_proxy_managed()),
                    title=provider.name,
                    list_heading="Connect Provider Connection",
                    footer=_PROXY_MANAGED_PROVIDER_FOOTER if self._is_proxy_managed() else None,
                )
            return

        self._palette.open_choice(
            "Connect OpenAI using:",
            [
                DialogChoice(
                    label=oauth_selection.label,
                    on_select=lambda: self._select_connection(oauth_selection),
                ),
                DialogChoice(
                    label=api_key_selection.label,
                    on_select=lambda: self._select_connection(api_key_selection),
                ),
            ],
        )

    def _select_connection(self, selection: ProviderConnectionSelection) -> None:
        if self._settings.core.credential_mode == "proxy-managed":
            self._palette.close_all_overlays()
            return
        if selection.connection.auth == "oauth":
            self._select_oauth_provider(selection)
            return
        self._palette.open_text_dialog(
            title=f"Enter {selection.label}",
            mask_input=True,
            on_submit=lambda key: self._submit_api_key(selection, key),
        )

    def select(self, item: ProviderDefinition | ProviderConnectionSelection) -> None:
        """Handle provider or provider connection selection."""
        if isinstance(item, ProviderConnectionSelection):
            self._select_connection(item)
            return
        self._open_provider_connections(item)
