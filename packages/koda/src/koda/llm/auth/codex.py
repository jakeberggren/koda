from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
from contextlib import suppress
from dataclasses import dataclass
from threading import Event
from time import time
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from koda.llm.auth.callback import OAuthCallbackListener
from koda.llm.auth.exceptions import (
    OAuthCallbackCancelledError,
    OAuthCallbackStateError,
    OpenAICodexAccountMissingError,
    OpenAICodexTokenError,
)
from koda.llm.auth.protocols import OAuthTokenClient, OAuthTokenResponse
from koda_common.logging import get_logger
from koda_common.settings.credentials import OAuthCredential

log = get_logger(__name__)

if TYPE_CHECKING:
    from koda.llm.auth.protocols import OAuthLoginCallbacks


CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"  # noqa: S105
REDIRECT_URI = "http://localhost:1455/auth/callback"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 1455
CALLBACK_PATH = "/auth/callback"
SCOPE = "openid profile email offline_access api.connectors.read api.connectors.invoke"
JWT_CLAIM_PATH = "https://api.openai.com/auth"
CODEX_ACCOUNT_ID_METADATA_KEY = "chatgpt_account_id"
JWT_PART_COUNT = 3
MANUAL_CODE_PROMPT = "Paste the full localhost callback URL from your browser here after login."


@dataclass(frozen=True, slots=True)
class AuthorizationFlow:
    """State needed to complete an OAuth authorization-code flow."""

    url: str
    state: str
    code_verifier: str

    @staticmethod
    def _code_challenge(code_verifier: str) -> str:
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    @classmethod
    def create(cls, *, originator: str = "koda") -> AuthorizationFlow:
        """Create an OpenAI Codex OAuth authorization URL with PKCE enabled."""

        state = secrets.token_urlsafe(24)
        code_verifier = secrets.token_urlsafe(64)
        query = urlencode(
            {
                "client_id": CLIENT_ID,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPE,
                "state": state,
                "code_challenge": cls._code_challenge(code_verifier),
                "code_challenge_method": "S256",
                "id_token_add_organizations": "true",
                "codex_cli_simplified_flow": "true",
                "originator": originator,
            }
        )
        return cls(
            url=f"{AUTHORIZE_URL}?{query}",
            state=state,
            code_verifier=code_verifier,
        )

    def extract_authorization_code(self, value: str) -> str:
        """Extract an OAuth authorization code from a callback URL or raw pasted code."""

        text = value.strip()
        parsed = urlparse(text)
        if parsed.query:
            params = parse_qs(parsed.query)
            state = params.get("state", [None])[0]
            if state != self.state:
                raise OAuthCallbackStateError
            code = params.get("code", [None])[0]
            if code:
                return code
        return text


class CodexOAuthTokenClient(OAuthTokenClient):
    """HTTP client for OpenAI Codex OAuth token operations."""

    @staticmethod
    def _required_token_string(
        data: dict[str, object],
        key: str,
        *,
        operation: str,
    ) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise OpenAICodexTokenError(operation, f"response missing string field: {key}")
        return value

    @staticmethod
    def _optional_token_int(
        data: dict[str, object],
        key: str,
        *,
        operation: str,
    ) -> int | None:
        value = data.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | str):
            raise OpenAICodexTokenError(operation, f"response field was not an integer: {key}")
        try:
            return int(value)
        except ValueError as error:
            raise OpenAICodexTokenError(
                operation,
                f"response field was not an integer: {key}",
            ) from error

    @classmethod
    def _parse_token_response(
        cls,
        response: httpx.Response,
        *,
        operation: str,
    ) -> OAuthTokenResponse:
        if response.is_error:
            raise OpenAICodexTokenError(
                operation,
                f"HTTP {response.status_code}: {response.text}",
            )
        try:
            data = response.json()
        except ValueError as error:
            raise OpenAICodexTokenError(operation, "response was not valid JSON") from error
        if not isinstance(data, dict):
            raise OpenAICodexTokenError(operation, "response JSON was not an object")

        token = {str(key): value for key, value in data.items()}
        return OAuthTokenResponse(
            access_token=cls._required_token_string(
                token,
                "access_token",
                operation=operation,
            ),
            refresh_token=cls._required_token_string(
                token,
                "refresh_token",
                operation=operation,
            ),
            expires_at=cls._optional_token_int(token, "expires_at", operation=operation),
            expires_in=cls._optional_token_int(token, "expires_in", operation=operation),
        )

    async def _post_token(
        self,
        data: dict[str, str],
        *,
        operation: Literal["exchange", "refresh"],
    ) -> OAuthTokenResponse:
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.post(TOKEN_URL, data=data)
        return self._parse_token_response(response, operation=operation)

    async def exchange_code(self, code: str, code_verifier: str) -> OAuthTokenResponse:
        """Exchange an authorization code for OpenAI Codex OAuth credentials."""

        return await self._post_token(
            {
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": code_verifier,
            },
            operation="exchange",
        )

    async def refresh_token(self, refresh_token: str) -> OAuthTokenResponse:
        """Refresh OpenAI Codex OAuth credentials."""

        return await self._post_token(
            {
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": refresh_token,
            },
            operation="refresh",
        )


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != JWT_PART_COUNT:
        return None
    try:
        payload = json.loads(_base64url_decode(parts[1]))
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def extract_account_id(access_token: str) -> str | None:
    """Return the ChatGPT account id embedded in an OpenAI Codex access token."""

    payload = _decode_jwt_payload(access_token)
    auth_claim = payload.get(JWT_CLAIM_PATH) if payload else None
    if not isinstance(auth_claim, dict):
        return None
    account_id = auth_claim.get("chatgpt_account_id")
    return account_id if isinstance(account_id, str) and account_id else None


class OpenAICodexProviderAuth:
    """OpenAI Codex OAuth provider auth using ChatGPT subscription login."""

    id = "openai:oauth"

    def __init__(
        self,
        *,
        token_client: OAuthTokenClient,
    ) -> None:
        self._token_client = token_client

    @staticmethod
    def _token_expires_at(token: OAuthTokenResponse) -> int:
        if token.expires_at is not None:
            return token.expires_at
        if token.expires_in is not None:
            return int(time() + token.expires_in)
        raise OpenAICodexTokenError("credential", "response missing expiry field")

    @classmethod
    def _credential_from_token(cls, token: OAuthTokenResponse) -> OAuthCredential:
        """Convert an OpenAI Codex OAuth token response into persisted credentials."""

        account_id = extract_account_id(token.access_token)
        log.info(
            "codex_oauth_credential_created",
            account_id=account_id,
            has_refresh_token=bool(token.refresh_token),
        )
        if account_id is None:
            raise OpenAICodexAccountMissingError
        return OAuthCredential(
            type="oauth",
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=str(cls._token_expires_at(token)),
            metadata={CODEX_ACCOUNT_ID_METADATA_KEY: account_id},
        )

    async def _exchange_authorization_code(
        self,
        code: str,
        code_verifier: str,
    ) -> OAuthCredential:
        """Exchange an authorization code for OpenAI Codex OAuth credentials."""

        log.info("codex_oauth_exchanging_code", token_url=TOKEN_URL)
        token = await self._token_client.exchange_code(code, code_verifier)
        log.info(
            "codex_oauth_token_fetched",
            has_refresh_token=bool(token.refresh_token),
            has_expires_at=token.expires_at is not None,
            has_expires_in=token.expires_in is not None,
        )
        return self._credential_from_token(token)

    async def _authorization_code_from_callback_or_prompt(
        self,
        flow: AuthorizationFlow,
        callbacks: OAuthLoginCallbacks,
    ) -> str:
        log.info("codex_oauth_waiting_for_callback", redirect_uri=REDIRECT_URI)
        cancel_callback = Event()
        callback_listener = OAuthCallbackListener(
            host=CALLBACK_HOST,
            port=CALLBACK_PORT,
            callback_path=CALLBACK_PATH,
            state=flow.state,
        )
        callback_task = asyncio.create_task(
            asyncio.to_thread(callback_listener.receive, cancel_event=cancel_callback)
        )
        prompt_task = asyncio.ensure_future(callbacks.on_prompt(MANUAL_CODE_PROMPT))
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
                return flow.extract_authorization_code(prompt_task.result())
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

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
        """Run the OpenAI Codex browser login flow."""

        flow = AuthorizationFlow.create()
        log.info("codex_oauth_auth_url_generated", state=flow.state[:8] + "...")
        callbacks.on_auth_url(flow.url)
        code = await self._authorization_code_from_callback_or_prompt(flow, callbacks)
        log.info("codex_oauth_callback_received", code_prefix=code[:8] if code else None)
        return await self._exchange_authorization_code(code, flow.code_verifier)

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        """Refresh an existing OpenAI Codex OAuth credential."""

        token = await self._token_client.refresh_token(credential.refresh_token)
        return self._credential_from_token(token)
