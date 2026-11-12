"""Tests for the model menu."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from koda.llm import ApiKeyCredential, Catalog
from koda_tui.palette.menus.models import ModelMenu
from koda_tui.settings import Settings

if TYPE_CHECKING:
    from koda.llm import ProviderCredential
    from koda_tui.palette.context import PaletteContext


class _Credentials:
    """An API key for every connection."""

    def get_credential(self, key: str) -> ProviderCredential | None:
        return ApiKeyCredential(type="api_key", value="key") if key.endswith(":api-key") else None

    def set_credential(self, key: str, credential: ProviderCredential) -> None:
        raise NotImplementedError


def test_the_active_model_is_current(
    context: PaletteContext,
) -> None:
    catalog, _warnings = Catalog.load()
    credentials = _Credentials()
    context.state.settings = Settings(provider="bergetai", model="google/gemma-4-31b-it")
    context.state.active_model = catalog.model("bergetai", "google/gemma-4-31b-it")
    context = replace(context, catalog=catalog, credentials=credentials)

    [current] = [item for item in ModelMenu(context).items() if item.current]
    assert current.data.id == "google/gemma-4-31B-it"
