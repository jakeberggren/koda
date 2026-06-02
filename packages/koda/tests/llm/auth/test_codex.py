# ruff: noqa: SLF001 - allow private member access for tests
from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from koda.llm.auth.codex import (
    AUTHORIZE_URL,
    CLIENT_ID,
    REDIRECT_URI,
    SCOPE,
    TOKEN_URL,
    AuthorizationFlow,
    CodexOAuthTokenClient,
    OpenAICodexProviderAuth,
    extract_account_id,
)
from koda.llm.auth.exceptions import OAuthCallbackStateError, OpenAICodexAccountMissingError
from koda.llm.auth.protocols import OAuthTokenResponse
from koda_common.settings.credentials import OAuthCredential


class _FakeTokenClient:
    def __init__(self) -> None:
        self.exchange_code_calls: list[tuple[str, str]] = []
        self.refresh_token_calls: list[str] = []

    async def exchange_code(self, code: str, code_verifier: str) -> OAuthTokenResponse:
        self.exchange_code_calls.append((code, code_verifier))
        return _token()

    async def refresh_token(self, refresh_token: str) -> OAuthTokenResponse:
        self.refresh_token_calls.append(refresh_token)
        return _token(access_token=_access_token("refreshed-account"), refresh="new-refresh")


def _jwt(payload: dict[str, object]) -> str:
    raw = json.dumps(payload).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"header.{encoded}.signature"


def _access_token(account_id: str = "account-id") -> str:
    return _jwt({"https://api.openai.com/auth": {"chatgpt_account_id": account_id}})


def _refresh_token() -> str:
    return "refresh-token"


def _token(
    *,
    access_token: str | None = None,
    refresh: str | None = None,
) -> OAuthTokenResponse:
    return OAuthTokenResponse(
        access_token=access_token or _access_token(),
        refresh_token=refresh or _refresh_token(),
        expires_at=123456,
    )


def _token_json(
    *,
    access_token: str | None = None,
    refresh: str | None = None,
) -> dict[str, object]:
    return {
        "access_token": access_token or _access_token(),
        "refresh_token": refresh or _refresh_token(),
        "expires_at": 123456,
    }


def _json_response(payload: dict[str, object]) -> httpx.Response:
    return httpx.Response(200, json=payload)


def test_extract_account_id_from_codex_access_token() -> None:
    token = _jwt(
        {
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "account-id",
            }
        }
    )

    assert extract_account_id(token) == "account-id"


def test_extract_account_id_returns_none_for_invalid_tokens() -> None:
    assert extract_account_id("not-a-jwt") is None
    assert extract_account_id(_jwt({})) is None
    assert extract_account_id(_jwt({"https://api.openai.com/auth": {}})) is None


def test_extract_authorization_code_from_callback_url() -> None:
    flow = AuthorizationFlow(url="", state="expected-state", code_verifier="")

    code = flow.extract_authorization_code(
        "http://localhost:1455/auth/callback?code=auth-code&state=expected-state"
    )

    assert code == "auth-code"


def test_extract_authorization_code_accepts_raw_code() -> None:
    flow = AuthorizationFlow(url="", state="expected-state", code_verifier="")

    assert flow.extract_authorization_code(" auth-code ") == "auth-code"


def test_extract_authorization_code_raises_on_state_mismatch() -> None:
    flow = AuthorizationFlow(url="", state="expected-state", code_verifier="")

    with pytest.raises(OAuthCallbackStateError):
        flow.extract_authorization_code(
            "http://localhost:1455/auth/callback?code=auth-code&state=wrong-state"
        )


def test_create_authorization_flow_contains_codex_parameters() -> None:
    flow = AuthorizationFlow.create(originator="koda-test")
    url = urlparse(flow.url)
    params = parse_qs(url.query)

    assert f"{url.scheme}://{url.netloc}{url.path}" == AUTHORIZE_URL
    assert params["client_id"] == [CLIENT_ID]
    assert params["redirect_uri"] == [REDIRECT_URI]
    assert params["scope"] == [SCOPE]
    assert params["response_type"] == ["code"]
    assert params["state"] == [flow.state]
    assert params["code_challenge_method"] == ["S256"]
    assert params["id_token_add_organizations"] == ["true"]
    assert params["codex_cli_simplified_flow"] == ["true"]
    assert params["originator"] == ["koda-test"]
    assert flow.code_verifier
    assert params["code_challenge"][0] != flow.code_verifier


def test_credential_from_token_extracts_oauth_credential() -> None:
    auth = OpenAICodexProviderAuth(token_client=_FakeTokenClient())

    credential = auth._credential_from_token(_token())

    assert credential == OAuthCredential(
        type="oauth",
        access_token=_access_token(),
        refresh_token=_refresh_token(),
        expires_at="123456",
        metadata={"chatgpt_account_id": "account-id"},
    )


def test_credential_from_token_raises_without_account_id() -> None:
    auth = OpenAICodexProviderAuth(token_client=_FakeTokenClient())

    with pytest.raises(OpenAICodexAccountMissingError):
        auth._credential_from_token(_token(access_token=_jwt({})))


async def test_exchange_code_uses_code_and_verifier() -> None:
    token_client = _FakeTokenClient()
    auth = OpenAICodexProviderAuth(token_client=token_client)

    credential = await auth._exchange_authorization_code("auth-code", "verifier")

    assert credential.metadata["chatgpt_account_id"] == "account-id"
    assert token_client.exchange_code_calls == [("auth-code", "verifier")]


async def test_token_client_exchanges_code_with_form_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(_token_json())

    monkeypatch.setattr(
        "koda.llm.auth.codex.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )

    token = await CodexOAuthTokenClient().exchange_code("auth-code", "verifier")

    assert token.access_token == _access_token()
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == TOKEN_URL
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"
    assert parse_qs(request.content.decode("utf-8")) == {
        "grant_type": ["authorization_code"],
        "client_id": [CLIENT_ID],
        "code": ["auth-code"],
        "redirect_uri": [REDIRECT_URI],
        "code_verifier": ["verifier"],
    }


async def test_refresh_uses_refresh_token() -> None:
    token_client = _FakeTokenClient()
    auth = OpenAICodexProviderAuth(token_client=token_client)

    credential = await auth.refresh(
        OAuthCredential(
            type="oauth",
            access_token="old-access",  # noqa: S106
            refresh_token="old-refresh",  # noqa: S106
            expires_at="1",
            metadata={"chatgpt_account_id": "old-account"},
        )
    )

    assert credential.metadata["chatgpt_account_id"] == "refreshed-account"
    assert credential.refresh_token == "new-refresh"  # noqa: S105
    assert token_client.refresh_token_calls == ["old-refresh"]
