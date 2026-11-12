"""Tests for the model menu."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from koda.llm import ApiKeyCredential, Catalog
from koda_tui.palette.menus.models import ModelMenu
from koda_tui.settings import Settings
from koda_tui.state import AppState

if TYPE_CHECKING:
    from koda.llm import ProviderCredential
    from koda_tui.palette.context import PaletteContext


class _Credentials:
    """An API key for every connection."""

    def get_credential(self, key: str) -> ProviderCredential | None:
        return ApiKeyCredential(type="api_key", value="key") if key.endswith(":api-key") else None

    def set_credential(self, key: str, credential: ProviderCredential) -> None:
        raise NotImplementedError


def test_the_selected_model_is_current_whatever_the_case_of_its_saved_id(
    context: PaletteContext,
) -> None:
    catalog, _warnings = Catalog.load()
    credentials = _Credentials()
    settings = Settings(provider="bergetai", model="google/gemma-4-31b-it")
    state = AppState.load(Path("/workspace"), settings, catalog=catalog, credentials=credentials)
    context = replace(context, catalog=catalog, credentials=credentials, state=state)

    [current] = [item for item in ModelMenu(context).items() if item.current]
    assert current.data.id == "google/gemma-4-31B-it"
