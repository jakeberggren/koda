from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from koda.llm.auth.browser import (
    AuthorizationRequest,
    LoopbackRedirect,
    complete_browser_authorization,
    extract_authorization_code,
)
from koda.llm.auth.exceptions import (
    OAuthCallbackCodeMissingError,
    OAuthCallbackRedirectError,
    OAuthCallbackStateError,
)
from koda.llm.auth.protocols import OAuthLoginCallbacks


def _request() -> AuthorizationRequest:
    return AuthorizationRequest(
        url="https://auth.example/login",
        redirect_uri="http://localhost/callback",
        state="expected-state",
        nonce="expected-nonce",
        code_verifier="verifier",
    )


def test_extract_authorization_code_from_callback_url() -> None:
    code = extract_authorization_code(
        _request(),
        "http://localhost/callback?code=auth-code&state=expected-state",
    )

    assert code == "auth-code"


@pytest.mark.parametrize(
    ("value", "error"),
    [
        ("auth-code", OAuthCallbackRedirectError),
        ("http://localhost/callback?state=expected-state", OAuthCallbackCodeMissingError),
        (
            "http://localhost/callback?code=auth-code&state=wrong-state",
            OAuthCallbackStateError,
        ),
    ],
)
def test_extract_authorization_code_rejects_invalid_callback(
    value: str,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        extract_authorization_code(_request(), value)


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/callback?code=auth-code&state=expected-state",
        "http://localhost/other?code=auth-code&state=expected-state",
    ],
)
def test_extract_authorization_code_rejects_unexpected_redirect(value: str) -> None:
    with pytest.raises(OAuthCallbackRedirectError):
        extract_authorization_code(_request(), value)


async def test_complete_browser_authorization_uses_loopback_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened_urls: list[str] = []

    def receive(self: object, *, cancel_event: object) -> str:
        _ = self
        _ = cancel_event
        return "auth-code"

    async def wait_for_prompt(_: str) -> str:
        await asyncio.Future()
        raise AssertionError

    monkeypatch.setattr("koda.llm.auth.browser.OAuthCallbackListener.receive", receive)
    callbacks = OAuthLoginCallbacks(
        on_auth_url=opened_urls.append,
        on_prompt=AsyncMock(side_effect=wait_for_prompt),
    )

    code = await complete_browser_authorization(
        _request(),
        callbacks,
        redirect=LoopbackRedirect(host="127.0.0.1", port=1455, path="/callback"),
        prompt="Paste callback URL",
    )

    assert code == "auth-code"
    assert opened_urls == ["https://auth.example/login"]
