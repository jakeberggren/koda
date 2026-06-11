from __future__ import annotations

from dataclasses import dataclass, replace
from time import time
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey

from koda.llm.auth.codex import (
    AUTHORIZE_URL,
    CLIENT_ID,
    EXPECTED_ID_TOKEN_ISSUER,
    JWKS_URL,
    REDIRECT_URI,
    SCOPE,
    TOKEN_URL,
    OpenAICodexAuth,
    create_authorization_request,
)
from koda.llm.auth.exceptions import OpenAICodexAccountMissingError, OpenAICodexTokenError
from koda.llm.auth.protocols import OAuthLoginCallbacks
from koda_common.settings.credentials import OAuthCredential

if TYPE_CHECKING:
    from koda.llm.auth.browser import AuthorizationRequest

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class _IdTokenClaims:
    account_id: str | None = "account-id"
    issuer: str = EXPECTED_ID_TOKEN_ISSUER
    audience: JsonValue = CLIENT_ID
    subject: str | None = "subject-id"
    expires_at: int | None = None
    issued_at: int | None = None
    include_issued_at: bool = True
    nonce: str | None = None


class _BrowserAuthorizer:
    def __init__(self, code: str = "auth-code") -> None:
        self.code = code
        self.request: AuthorizationRequest | None = None

    async def __call__(
        self,
        request: AuthorizationRequest,
        callbacks: OAuthLoginCallbacks,
    ) -> str:
        self.request = request
        callbacks.on_auth_url(request.url)
        return self.code


def _signed_id_token(key: RSAKey, config: _IdTokenClaims) -> str:
    claims: JsonObject = {
        "iss": config.issuer,
        "aud": config.audience,
        "exp": config.expires_at if config.expires_at is not None else int(time()) + 300,
    }
    if config.subject is not None:
        claims["sub"] = config.subject
    if config.include_issued_at:
        claims["iat"] = config.issued_at if config.issued_at is not None else int(time())
    if config.nonce is not None:
        claims["nonce"] = config.nonce
    if config.account_id is not None:
        claims["https://api.openai.com/auth"] = {
            "chatgpt_account_id": config.account_id,
        }
    return jwt.encode({"alg": "RS256", "kid": "test-key"}, claims, key, algorithms=["RS256"])


def _jwks_transport(key: RSAKey) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == JWKS_URL
        return httpx.Response(200, json={"keys": [key.as_dict(private=False)]})

    return httpx.MockTransport(handler)


def _callbacks(opened_urls: list[str] | None = None) -> OAuthLoginCallbacks:
    urls = opened_urls if opened_urls is not None else []
    return OAuthLoginCallbacks(
        on_auth_url=urls.append,
        on_prompt=AsyncMock(),
    )


def test_create_authorization_request_contains_codex_parameters() -> None:
    request = create_authorization_request(originator="koda-test")
    url = urlparse(request.url)
    params = parse_qs(url.query)

    assert f"{url.scheme}://{url.netloc}{url.path}" == AUTHORIZE_URL
    assert params["client_id"] == [CLIENT_ID]
    assert params["redirect_uri"] == [REDIRECT_URI]
    assert params["scope"] == [SCOPE]
    assert params["response_type"] == ["code"]
    assert params["state"] == [request.state]
    assert params["nonce"] == [request.nonce]
    assert params["code_challenge_method"] == ["S256"]
    assert params["id_token_add_organizations"] == ["true"]
    assert params["codex_cli_simplified_flow"] == ["true"]
    assert params["originator"] == ["koda-test"]
    assert params["code_challenge"][0] != request.code_verifier


async def test_login_exchanges_code_and_builds_credential() -> None:
    key = RSAKey.generate_key(parameters={"kid": "test-key"}, private=True)
    browser = _BrowserAuthorizer()
    token_requests: list[httpx.Request] = []

    def token_handler(request: httpx.Request) -> httpx.Response:
        token_requests.append(request)
        assert browser.request is not None
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "id_token": _signed_id_token(
                    key,
                    _IdTokenClaims(
                        audience=[CLIENT_ID],
                        nonce=browser.request.nonce,
                    ),
                ),
                "expires_at": 123456,
            },
        )

    auth = OpenAICodexAuth(
        browser_authorizer=browser,
        oauth_transport=httpx.MockTransport(token_handler),
        jwks_transport=_jwks_transport(key),
    )
    opened_urls: list[str] = []

    credential = await auth.login(_callbacks(opened_urls))

    assert credential == OAuthCredential(
        type="oauth",
        access_token="access-token",  # noqa: S106
        refresh_token="refresh-token",  # noqa: S106
        expires_at="123456",
        metadata={"chatgpt_account_id": "account-id"},
    )
    assert browser.request is not None
    assert opened_urls == [browser.request.url]
    assert len(token_requests) == 1
    assert str(token_requests[0].url) == TOKEN_URL
    assert parse_qs(token_requests[0].content.decode()) == {
        "grant_type": ["authorization_code"],
        "client_id": [CLIENT_ID],
        "code": ["auth-code"],
        "redirect_uri": [REDIRECT_URI],
        "code_verifier": [browser.request.code_verifier],
    }


async def test_refresh_preserves_fields_omitted_by_provider() -> None:
    token_requests: list[httpx.Request] = []

    def token_handler(request: httpx.Request) -> httpx.Response:
        token_requests.append(request)
        return httpx.Response(
            200,
            json={"access_token": "new-access", "expires_at": 123456},
        )

    auth = OpenAICodexAuth(oauth_transport=httpx.MockTransport(token_handler))
    old_credential = OAuthCredential(
        type="oauth",
        access_token="old-access",  # noqa: S106
        refresh_token="old-refresh",  # noqa: S106
        expires_at="1",
        metadata={"chatgpt_account_id": "old-account", "other": "value"},
    )

    credential = await auth.refresh(old_credential)

    assert credential == OAuthCredential(
        type="oauth",
        access_token="new-access",  # noqa: S106
        refresh_token="old-refresh",  # noqa: S106
        expires_at="123456",
        metadata={"chatgpt_account_id": "old-account", "other": "value"},
    )
    assert parse_qs(token_requests[0].content.decode()) == {
        "grant_type": ["refresh_token"],
        "client_id": [CLIENT_ID],
        "refresh_token": ["old-refresh"],
        "scope": [SCOPE],
    }


async def test_refresh_validates_new_id_token() -> None:
    key = RSAKey.generate_key(parameters={"kid": "test-key"}, private=True)

    def token_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "id_token": _signed_id_token(
                    key,
                    _IdTokenClaims(account_id="new-account"),
                ),
                "expires_at": 123456,
            },
        )

    auth = OpenAICodexAuth(
        oauth_transport=httpx.MockTransport(token_handler),
        jwks_transport=_jwks_transport(key),
    )
    old_credential = OAuthCredential(
        type="oauth",
        access_token="old-access",  # noqa: S106
        refresh_token="old-refresh",  # noqa: S106
        expires_at="1",
        metadata={"chatgpt_account_id": "old-account"},
    )

    credential = await auth.refresh(old_credential)

    assert credential.refresh_token == "new-refresh"  # noqa: S105
    assert credential.metadata["chatgpt_account_id"] == "new-account"


@pytest.mark.parametrize(
    "claims",
    [
        _IdTokenClaims(issuer="https://evil.example/"),
        _IdTokenClaims(audience="wrong-client"),
        _IdTokenClaims(subject=None),
        _IdTokenClaims(expires_at=1),
        _IdTokenClaims(include_issued_at=False),
        _IdTokenClaims(issued_at=int(time()) + 300),
        _IdTokenClaims(nonce="wrong-nonce"),
    ],
)
async def test_login_rejects_invalid_id_token_claims(claims: _IdTokenClaims) -> None:
    key = RSAKey.generate_key(parameters={"kid": "test-key"}, private=True)
    browser = _BrowserAuthorizer()

    def token_handler(_: httpx.Request) -> httpx.Response:
        assert browser.request is not None
        config = (
            claims if claims.nonce is not None else replace(claims, nonce=browser.request.nonce)
        )
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "id_token": _signed_id_token(key, config),
                "expires_at": 123456,
            },
        )

    auth = OpenAICodexAuth(
        browser_authorizer=browser,
        oauth_transport=httpx.MockTransport(token_handler),
        jwks_transport=_jwks_transport(key),
    )

    with pytest.raises(OpenAICodexTokenError):
        await auth.login(_callbacks())


async def test_login_rejects_missing_account_id() -> None:
    key = RSAKey.generate_key(parameters={"kid": "test-key"}, private=True)
    browser = _BrowserAuthorizer()

    def token_handler(_: httpx.Request) -> httpx.Response:
        assert browser.request is not None
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "id_token": _signed_id_token(
                    key,
                    _IdTokenClaims(account_id=None, nonce=browser.request.nonce),
                ),
                "expires_at": 123456,
            },
        )

    auth = OpenAICodexAuth(
        browser_authorizer=browser,
        oauth_transport=httpx.MockTransport(token_handler),
        jwks_transport=_jwks_transport(key),
    )

    with pytest.raises(OpenAICodexAccountMissingError):
        await auth.login(_callbacks())


async def test_login_rejects_invalid_token_response() -> None:
    auth = OpenAICodexAuth(
        browser_authorizer=_BrowserAuthorizer(),
        oauth_transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
    )

    with pytest.raises(OpenAICodexTokenError, match="response JSON was invalid"):
        await auth.login(_callbacks())
