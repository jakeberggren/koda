from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from koda.llm import ApiKeyCredential, JsonCredentialStore, OAuthCredential
from koda.llm.exceptions import CredentialsError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def _oauth() -> OAuthCredential:
    return OAuthCredential(
        type="oauth",
        access_token="access",  # noqa: S106
        refresh_token="refresh",  # noqa: S106
        expires_at="123",
    )


def test_a_missing_file_has_no_credentials(tmp_path: Path) -> None:
    assert JsonCredentialStore(tmp_path / "credentials.json").get_credential("openai:oauth") is None


def test_credentials_are_kept_in_a_file_only_the_user_can_read(tmp_path: Path) -> None:
    path = tmp_path / "koda" / "credentials.json"
    JsonCredentialStore(path).set_credential("openai:oauth", _oauth())
    JsonCredentialStore(path).set_credential(
        "anthropic:api-key", ApiKeyCredential(type="api_key", value="key")
    )

    store = JsonCredentialStore(path)
    assert store.get_credential("openai:oauth") == _oauth()
    assert store.get_credential("anthropic:api-key") == ApiKeyCredential(
        type="api_key", value="key"
    )
    assert path.stat().st_mode & 0o777 == 0o600


def test_an_api_key_in_the_environment_comes_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = JsonCredentialStore(tmp_path / "credentials.json")
    store.set_credential("openai:api-key", ApiKeyCredential(type="api_key", value="stored"))
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")

    assert store.get_credential("openai:api-key") == ApiKeyCredential(
        type="api_key", value="from-env"
    )
    assert store.get_credential("openai:oauth") is None


def test_a_broken_file_says_where(tmp_path: Path) -> None:
    path = tmp_path / "credentials.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(CredentialsError, match=str(path)):
        JsonCredentialStore(path).get_credential("openai:oauth")
