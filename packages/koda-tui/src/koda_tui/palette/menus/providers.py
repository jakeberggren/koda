"""Provider palette items and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from koda_common.logging import get_logger
from koda_tui import actions
from koda_tui.palette.items import ListItem

if TYPE_CHECKING:
    from prompt_toolkit.formatted_text import StyleAndTextTuples

    from koda.llm import ProviderDefinition
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


class ProviderMenu:
    """Provider submenu behavior."""

    def __init__(self, palette: Palette) -> None:
        self._palette = palette
        self._service = palette.service
        self._settings = palette.app_settings

    def _is_proxy_managed(self) -> bool:
        return self._settings.core.credential_mode == "proxy-managed"

    def _items(self, *, proxy_managed: bool) -> list[ListItem]:
        """Build provider selection items."""
        connected = {p.id for p in self._service.list_configured_providers()}
        return [
            ListItem(
                id=f"select_provider:{provider.id}",
                label=provider.name,
                description=provider.description or "",
                marker="✓" if provider.id in connected and not proxy_managed else None,
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
            actions.select_model(None, models[0], self._settings.core)

    def _submit_api_key(self, provider: ProviderDefinition, key: str) -> None:
        result = actions.set_provider_api_key(provider.id, key, self._settings.core)
        if not result.ok:
            log.warning("set_api_key_failed", provider=provider.id, error=result.error)
            return
        self._auto_select_first_model(provider)
        self._palette.close_all_overlays()

    def select(self, provider: ProviderDefinition) -> None:
        """Handle provider selection."""
        if self._settings.core.credential_mode == "proxy-managed":
            self._palette.close_all_overlays()
            return
        self._palette.open_text_dialog(
            title=f"Enter {provider.name} API Key",
            mask_input=True,
            on_submit=lambda key: self._submit_api_key(provider, key),
        )
