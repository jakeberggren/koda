from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from koda.llm.auth.callback import OAuthCallbackListener, extract_callback_code
from koda.llm.auth.exceptions import OAuthCallbackCancelledError, OAuthCallbackRedirectError

if TYPE_CHECKING:
    from koda.llm.auth.protocols import OAuthLoginCallbacks


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorizationRequest:
    """Browser authorization URL and state needed to complete the code flow."""

    url: str
    redirect_uri: str
    state: str
    code_verifier: str
    nonce: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class LoopbackRedirect:
    """Local redirect endpoint used to receive an OAuth callback."""

    host: str
    port: int
    path: str


def _matches_redirect(callback_url: str, redirect_uri: str) -> bool:
    callback = urlparse(callback_url)
    expected = urlparse(redirect_uri)
    return (
        callback.scheme.lower() == expected.scheme.lower()
        and callback.hostname == expected.hostname
        and callback.port == expected.port
        and callback.path == expected.path
        and callback.username is None
        and callback.password is None
    )


def extract_authorization_code(request: AuthorizationRequest, callback_url: str) -> str:
    """Extract an authorization code from a pasted callback URL."""

    callback_url = callback_url.strip()
    if not _matches_redirect(callback_url, request.redirect_uri):
        raise OAuthCallbackRedirectError
    return extract_callback_code(urlparse(callback_url).query, expected_state=request.state)


async def complete_browser_authorization(
    request: AuthorizationRequest,
    callbacks: OAuthLoginCallbacks,
    *,
    redirect: LoopbackRedirect,
    prompt: str,
) -> str:
    """Open a browser login and return the first valid callback or pasted code."""

    callbacks.on_auth_url(request.url)
    cancel_callback = Event()
    listener = OAuthCallbackListener(
        host=redirect.host,
        port=redirect.port,
        callback_path=redirect.path,
        state=request.state,
    )
    callback_task = asyncio.create_task(
        asyncio.to_thread(listener.receive, cancel_event=cancel_callback)
    )
    prompt_task = asyncio.ensure_future(callbacks.on_prompt(prompt))
    try:
        done, pending = await asyncio.wait(
            {callback_task, prompt_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if prompt_task in done:
            cancel_callback.set()
            with suppress(asyncio.CancelledError, OAuthCallbackCancelledError):
                await callback_task
            return extract_authorization_code(request, prompt_task.result())
        prompt_task.cancel()
        return callback_task.result()
    finally:
        cancel_callback.set()
        if not prompt_task.done():
            prompt_task.cancel()
            with suppress(asyncio.CancelledError):
                await prompt_task
        if not callback_task.done():
            with suppress(asyncio.CancelledError, OAuthCallbackCancelledError):
                await callback_task
