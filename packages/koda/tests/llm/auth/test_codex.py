# ruff: noqa: SLF001 - allow private member access for tests
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from time import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from authlib.integrations.httpx_client import AsyncOAuth2Client
from joserfc import jwt
from joserfc.jwk import RSAKey

from koda.llm.auth.codex import (
    AUTHORIZE_URL,
    CLIENT_ID,
    EXPECTED_DISCOVERY_ISSUER,
    EXPECTED_ID_TOKEN_ISSUER,
    OIDC_DISCOVERY_URL,
    REDIRECT_URI,
    SCOPE,
    TOKEN_URL,
    CodexOAuthClient,
    OpenAICodexProviderAuth,
    extract_account_id,
    extract_authorization_code,
)
from koda.llm.auth.exceptions import (
    OAuthCallbackCodeMissingError,
    OAuthCallbackStateError,
    OpenAICodexAccountMissingError,
    OpenAICodexTokenError,
)
from koda.llm.auth.protocols import JsonObject, OAuthAuthorizationFlow
from koda_common.settings.credentials import OAuthCredential


class _FakeOAuthClient:
    def __init__(
        self,
        *,
        credential: OAuthCredential | None = None,
        exchange_error: Exception | None = None,
    ) -> None:
        self.flow = OAuthAuthorizationFlow(
            url="https://auth.example/login",
            state="expected-state",
            nonce="expected-nonce",
            code_verifier="verifier",
        )
        self.credential = credential or OAuthCredential(
            type="oauth",
            access_token="access-token",  # noqa: S106
            refresh_token="refresh-token",  # noqa: S106
            expires_at="123456",
            metadata={"chatgpt_account_id": "account-id"},
        )
        self.exchange_error = exchange_error
        self.create_authorization_flow_calls = 0
        self.exchange_code_calls: list[tuple[str, OAuthAuthorizationFlow]] = []
        self.refresh_calls: list[OAuthCredential] = []

    def create_authorization_flow(self, *, originator: str = "koda") -> OAuthAuthorizationFlow:
        self.create_authorization_flow_calls += 1
        return self.flow

    async def exchange_code(
        self,
        code: str,
        flow: OAuthAuthorizationFlow,
    ) -> OAuthCredential:
        self.exchange_code_calls.append((code, flow))
        if self.exchange_error is not None:
            raise self.exchange_error
        return self.credential

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        self.refresh_calls.append(credential)
        return self.credential


def _jwt(payload: JsonObject) -> str:
    raw = json.dumps(payload).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"header.{encoded}.signature"


def _account_claims(account_id: str = "account-id", *, nonce: str | None = None) -> JsonObject:
    claims: JsonObject = {"https://api.openai.com/auth": {"chatgpt_account_id": account_id}}
    if nonce is not None:
        claims["nonce"] = nonce
    return claims


def _id_token(account_id: str = "account-id", *, nonce: str | None = None) -> str:
    return _jwt(_account_claims(account_id, nonce=nonce))


@dataclass(frozen=True, slots=True)
class _IdTokenClaims:
    account_id: str = "account-id"
    issuer: str = EXPECTED_ID_TOKEN_ISSUER
    audience: str = CLIENT_ID
    expires_at: int | None = None
    nonce: str | None = "expected-nonce"


def _signed_id_token(key: RSAKey, claims_config: _IdTokenClaims | None = None) -> str:
    config = claims_config or _IdTokenClaims()
    claims = _account_claims(config.account_id, nonce=config.nonce)
    claims.update(
        {
            "iss": config.issuer,
            "aud": config.audience,
            "exp": config.expires_at if config.expires_at is not None else int(time()) + 300,
        }
    )
    return jwt.encode({"alg": "RS256", "kid": "test-key"}, claims, key, algorithms=["RS256"])


def _mock_openid_transport(
    key: RSAKey,
    *,
    issuer: str = EXPECTED_DISCOVERY_ISSUER,
    jwks_uri: str = "https://auth.openai.com/test-jwks.json",
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == OIDC_DISCOVERY_URL:
            return httpx.Response(200, json={"issuer": issuer, "jwks_uri": jwks_uri})
        if str(request.url) == jwks_uri:
            return httpx.Response(200, json={"keys": [key.as_dict(private=False)]})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _refresh_token() -> str:
    return "refresh-token"


def _token_json(
    *,
    access_token: str | None = None,
    id_token: str | None = None,
    refresh: str | None = None,
) -> JsonObject:
    return {
        "access_token": access_token or "opaque-access-token",
        "refresh_token": refresh or _refresh_token(),
        "id_token": id_token or _id_token(),
        "expires_at": 123456,
    }


def _json_response(payload: JsonObject) -> httpx.Response:
    return httpx.Response(200, json=payload)


def test_extract_account_id_from_codex_claims() -> None:
    assert extract_account_id(_account_claims()) == "account-id"


def test_extract_account_id_returns_none_for_invalid_claims() -> None:
    assert extract_account_id({}) is None
    assert extract_account_id({"https://api.openai.com/auth": {}}) is None


def test_extract_authorization_code_from_callback_url() -> None:
    flow = OAuthAuthorizationFlow(
        url="", state="expected-state", nonce="expected-nonce", code_verifier=""
    )

    code = extract_authorization_code(
        flow,
        "http://localhost:1455/auth/callback?code=auth-code&state=expected-state",
    )

    assert code == "auth-code"


def test_extract_authorization_code_rejects_raw_code() -> None:
    flow = OAuthAuthorizationFlow(
        url="", state="expected-state", nonce="expected-nonce", code_verifier=""
    )

    with pytest.raises(OAuthCallbackStateError):
        extract_authorization_code(flow, " auth-code ")


def test_extract_authorization_code_raises_without_code() -> None:
    flow = OAuthAuthorizationFlow(
        url="", state="expected-state", nonce="expected-nonce", code_verifier=""
    )

    with pytest.raises(OAuthCallbackCodeMissingError):
        extract_authorization_code(flow, "http://localhost:1455/auth/callback?state=expected-state")


def test_extract_authorization_code_raises_on_state_mismatch() -> None:
    flow = OAuthAuthorizationFlow(
        url="",
        state="expected-state",
        nonce="expected-nonce",
        code_verifier="",
    )

    with pytest.raises(OAuthCallbackStateError):
        extract_authorization_code(
            flow,
            "http://localhost:1455/auth/callback?code=auth-code&state=wrong-state",
        )


def test_create_authorization_flow_contains_codex_parameters() -> None:
    flow = CodexOAuthClient().create_authorization_flow(originator="koda-test")
    url = urlparse(flow.url)
    params = parse_qs(url.query)

    assert f"{url.scheme}://{url.netloc}{url.path}" == AUTHORIZE_URL
    assert params["client_id"] == [CLIENT_ID]
    assert params["redirect_uri"] == [REDIRECT_URI]
    assert params["scope"] == [SCOPE]
    assert params["response_type"] == ["code"]
    assert params["state"] == [flow.state]
    assert params["nonce"] == [flow.nonce]
    assert params["code_challenge_method"] == ["S256"]
    assert params["id_token_add_organizations"] == ["true"]
    assert params["codex_cli_simplified_flow"] == ["true"]
    assert params["originator"] == ["koda-test"]
    assert flow.code_verifier
    assert params["code_challenge"][0] != flow.code_verifier


def test_oauth_client_converts_validated_token_to_credential() -> None:
    client = CodexOAuthClient()
    token = client._parse_token_response(_token_json(), operation="exchange")

    credential = client._credential_from_token(token, _account_claims())

    assert credential == OAuthCredential(
        type="oauth",
        access_token="opaque-access-token",  # noqa: S106
        refresh_token=_refresh_token(),
        expires_at="123456",
        metadata={"chatgpt_account_id": "account-id"},
    )


def test_oauth_client_raises_without_account_id() -> None:
    client = CodexOAuthClient()
    token = client._parse_token_response(_token_json(), operation="exchange")

    with pytest.raises(OpenAICodexAccountMissingError):
        client._credential_from_token(token, {})


async def test_oauth_client_exchanges_code_with_form_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(_token_json())

    monkeypatch.setattr(
        "koda.llm.auth.codex.AsyncOAuth2Client",
        lambda **kwargs: AsyncOAuth2Client(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )

    flow = OAuthAuthorizationFlow(
        url="",
        state="",
        nonce="expected-nonce",
        code_verifier="verifier",
    )
    token = await CodexOAuthClient()._fetch_token("auth-code", flow)

    assert token.access_token == "opaque-access-token"  # noqa: S105
    assert token.id_token == _id_token()
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == TOKEN_URL
    assert request.headers["content-type"] == "application/x-www-form-urlencoded;charset=UTF-8"
    assert parse_qs(request.content.decode("utf-8")) == {
        "grant_type": ["authorization_code"],
        "client_id": [CLIENT_ID],
        "code": ["auth-code"],
        "redirect_uri": [REDIRECT_URI],
        "code_verifier": ["verifier"],
    }


async def test_provider_auth_delegates_refresh_to_oauth_client() -> None:
    oauth_client = _FakeOAuthClient()
    auth = OpenAICodexProviderAuth(oauth_client=oauth_client)
    old_credential = OAuthCredential(
        type="oauth",
        access_token="old-access",  # noqa: S106
        refresh_token="old-refresh",  # noqa: S106
        expires_at="1",
        metadata={"chatgpt_account_id": "old-account"},
    )

    credential = await auth.refresh(old_credential)

    assert credential == oauth_client.credential
    assert oauth_client.refresh_calls == [old_credential]


async def test_oauth_client_validates_signed_id_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = RSAKey.generate_key(parameters={"kid": "test-key"}, private=True)
    token = _signed_id_token(key, _IdTokenClaims(nonce="expected-nonce"))
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "koda.llm.auth.codex.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=_mock_openid_transport(key),
            **kwargs,
        ),
    )

    claims = await CodexOAuthClient()._validate_id_token(token, nonce="expected-nonce")

    assert extract_account_id(claims) == "account-id"


@pytest.mark.parametrize(
    ("claims_config", "expected_nonce"),
    [
        (_IdTokenClaims(issuer="https://evil.example/"), "expected-nonce"),
        (_IdTokenClaims(audience="wrong-client"), "expected-nonce"),
        (_IdTokenClaims(expires_at=1), "expected-nonce"),
        (_IdTokenClaims(nonce="wrong-nonce"), "expected-nonce"),
    ],
)
async def test_oauth_client_rejects_invalid_id_token_claims(
    monkeypatch: pytest.MonkeyPatch,
    claims_config: _IdTokenClaims,
    expected_nonce: str,
) -> None:
    key = RSAKey.generate_key(parameters={"kid": "test-key"}, private=True)
    token = _signed_id_token(key, claims_config)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "koda.llm.auth.codex.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=_mock_openid_transport(key),
            **kwargs,
        ),
    )

    with pytest.raises(OpenAICodexTokenError):
        await CodexOAuthClient()._validate_id_token(token, nonce=expected_nonce)


async def test_oauth_client_rejects_jwt_shaped_unsigned_id_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = RSAKey.generate_key(parameters={"kid": "test-key"}, private=True)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "koda.llm.auth.codex.httpx.AsyncClient",
        lambda **kwargs: real_async_client(
            transport=_mock_openid_transport(key),
            **kwargs,
        ),
    )

    with pytest.raises(OpenAICodexTokenError):
        await CodexOAuthClient()._validate_id_token(
            _id_token(nonce="expected-nonce"),
            nonce="expected-nonce",
        )
