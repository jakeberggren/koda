"""Tests for AppState.refresh: what stops Koda from responding, and the active model."""

from __future__ import annotations

from pathlib import Path

import pytest

from koda.llm import Catalog
from koda.llm.credentials import ApiKeyCredential, ProviderCredential
from koda.llm.exceptions import CredentialsError
from koda_tui import strings
from koda_tui.settings import Settings
from koda_tui.state import AppState


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    catalog, _warnings = Catalog.load()
    return catalog


class _Credentials(dict[str, ProviderCredential]):
    def get_credential(self, key: str) -> ProviderCredential | None:
        return self.get(key)

    def set_credential(self, key: str, credential: ProviderCredential) -> None:
        self[key] = credential


class _UnreadableCredentials(_Credentials):
    def get_credential(self, key: str) -> ProviderCredential | None:
        raise CredentialsError(Path("credentials.json"), PermissionError("denied"))


def _connected() -> _Credentials:
    return _Credentials({"openai:api-key": ApiKeyCredential(type="api_key", value="key")})


def _state(
    catalog: Catalog,
    provider: str | None = "openai",
    model: str | None = "gpt-5.2",
    credentials: _Credentials | None = None,
) -> AppState:
    return AppState.load(
        Path("/workspace"),
        Settings(provider=provider, model=model),
        catalog=catalog,
        credentials=_connected() if credentials is None else credentials,
    )


def test_the_selected_connected_model_is_active(catalog: Catalog) -> None:
    state = _state(catalog)

    assert state.issue is None
    assert state.active_model is not None
    assert state.active_model.id == "gpt-5.2"
    assert [provider.id for provider in state.configured_providers] == ["openai"]


def test_setup_is_required_without_credentials(catalog: Catalog) -> None:
    state = _state(catalog, credentials=_Credentials())

    assert state.issue == strings.Screen.Status.SETUP_REQUIRED


def test_selection_is_required_without_a_model(catalog: Catalog) -> None:
    state = _state(catalog, model=None)

    assert state.issue == strings.Screen.Status.SELECTION_REQUIRED
    assert state.active_model is None


def test_an_unknown_model_is_unavailable(catalog: Catalog) -> None:
    assert _state(catalog, model="missing").issue == (strings.Screen.Status.MODEL_UNAVAILABLE)


def test_a_model_of_an_unconnected_provider_is_unavailable(catalog: Catalog) -> None:
    state = _state(catalog, "bergetai", "google/gemma-4-31B-it")

    assert state.issue == strings.Screen.Status.MODEL_UNAVAILABLE


def test_an_unreadable_credentials_file_is_reported(catalog: Catalog) -> None:
    state = _state(catalog, credentials=_UnreadableCredentials())

    assert state.issue == strings.Screen.Status.CREDENTIALS_UNREADABLE
    assert state.configured_providers == []
