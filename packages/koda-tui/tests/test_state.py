"""Tests for AppState.refresh: what stops Koda from responding, and the active model."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from koda.llm import Catalog
from koda.llm.credentials import ApiKeyCredential
from koda_tui import strings
from koda_tui.settings import SecretsPermissionError
from koda_tui.state import AppState


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    catalog, _warnings = Catalog.load()
    return catalog


def _settings(provider: str | None = "openai", model: str | None = "gpt-5.2") -> Mock:
    settings = Mock()
    settings.provider, settings.model, settings.thinking = provider, model, "none"
    credentials = {"openai:api-key": ApiKeyCredential(type="api_key", value="key")}
    settings.get_credential.side_effect = credentials.get
    return settings


def _state(catalog: Catalog, settings: Mock) -> AppState:
    return AppState.load(Path("/workspace"), catalog, settings)


def test_the_selected_connected_model_is_active(catalog: Catalog) -> None:
    state = _state(catalog, _settings())

    assert state.issue is None
    assert state.active_model is not None
    assert state.active_model.id == "gpt-5.2"
    assert [provider.id for provider in state.configured_providers] == ["openai"]


def test_setup_is_required_without_credentials(catalog: Catalog) -> None:
    settings = _settings()
    settings.get_credential.side_effect = None
    settings.get_credential.return_value = None

    assert _state(catalog, settings).issue == strings.Screen.Status.SETUP_REQUIRED


def test_selection_is_required_without_a_model(catalog: Catalog) -> None:
    state = _state(catalog, _settings(model=None))

    assert state.issue == strings.Screen.Status.SELECTION_REQUIRED
    assert state.active_model is None


def test_an_unknown_model_is_unavailable(catalog: Catalog) -> None:
    assert _state(catalog, _settings(model="missing")).issue == (
        strings.Screen.Status.MODEL_UNAVAILABLE
    )


def test_a_model_of_an_unconnected_provider_is_unavailable(catalog: Catalog) -> None:
    state = _state(catalog, _settings("bergetai", "google/gemma-4-31B-it"))

    assert state.issue == strings.Screen.Status.MODEL_UNAVAILABLE


def test_an_unreadable_secrets_file_is_reported(catalog: Catalog) -> None:
    settings = _settings()
    settings.get_credential.side_effect = SecretsPermissionError(
        path=Path("secrets.json"), error=PermissionError("denied")
    )

    state = _state(catalog, settings)

    assert state.issue is not None
    assert state.configured_providers == []
