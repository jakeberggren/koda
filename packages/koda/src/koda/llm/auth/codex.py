from __future__ import annotations

import asyncio
import secrets
from contextlib import suppress
from threading import Event
from time import time
from typing import TYPE_CHECKING, Annotated, cast
from urllib.parse import urlparse

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.base import OAuth2Error
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet, import_key
from joserfc.jwt import JWTClaimsRegistry
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from koda.llm.auth.callback import OAuthCallbackListener, extract_callback_code
from koda.llm.auth.exceptions import (
    OAuthCallbackCancelledError,
    OpenAICodexAccountMissingError,
    OpenAICodexTokenError,
)
from koda.llm.auth.protocols import OAuthAuthorizationFlow, OAuthProviderClient
from koda_common.logging import get_logger
from koda_common.settings.credentials import OAuthCredential

log = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from koda.llm.auth.protocols import JsonObject, JsonValue, OAuthLoginCallbacks


type JwkDict = dict[str, str | list[str]]


CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"  # noqa: S105
OIDC_DISCOVERY_URL = "https://auth.openai.com/.well-known/openid-configuration"
EXPECTED_DISCOVERY_ISSUER = "https://auth0.openai.com/"
EXPECTED_ID_TOKEN_ISSUER = "https://auth.openai.com"  # noqa: S105
ID_TOKEN_ALGORITHMS = ["RS256", "PS256"]
JWKS_KEYS_FIELD = "keys"
ID_TOKEN_LEEWAY_SECONDS = 60
REDIRECT_URI = "http://localhost:1455/auth/callback"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 1455
CALLBACK_PATH = "/auth/callback"
SCOPE = "openid profile email offline_access api.connectors.read api.connectors.invoke"
JWT_CLAIM_PATH = "https://api.openai.com/auth"
CODEX_ACCOUNT_ID_METADATA_KEY = "chatgpt_account_id"
MANUAL_CODE_PROMPT = "Paste the full localhost callback URL from your browser here after login."
OPENID_CONFIGURATION_FETCH_FAILED = "openid configuration fetch failed"
OPENID_CONFIGURATION_INVALID = "openid configuration was invalid"
OPENID_ISSUER_MISMATCH = "openid issuer mismatch"
OPENID_JWKS_FETCH_FAILED = "openid jwks fetch failed"
OPENID_JWKS_INVALID = "openid jwks was invalid"
JWT_VALIDATION_FAILED = "id_token validation failed"
JWT_NONCE_MISMATCH = "id_token nonce mismatch"
RESPONSE_MISSING_EXPIRY_FIELD = "response missing expiry field"
RESPONSE_JSON_INVALID = "response JSON was invalid"


class CodexTokenResponsePayload(BaseModel):
    """Validated OpenAI Codex OAuth token endpoint response."""

    model_config = ConfigDict(extra="ignore")

    access_token: Annotated[StrictStr, Field(min_length=1)]
    refresh_token: Annotated[StrictStr, Field(min_length=1)]
    id_token: Annotated[StrictStr, Field(min_length=1)]
    expires_at: StrictInt | None = None
    expires_in: StrictInt | None = None


class OpenIDConfiguration(BaseModel):
    """Subset of OpenID discovery metadata needed to validate ID tokens."""

    model_config = ConfigDict(extra="ignore")

    issuer: StrictStr
    jwks_uri: StrictStr


class JWKS(BaseModel):
    """Validated JSON Web Key Set response."""

    model_config = ConfigDict(extra="ignore")

    keys: Annotated[list[JwkDict], Field(min_length=1)]


def extract_authorization_code(flow: OAuthAuthorizationFlow, value: str) -> str:
    """Extract an OAuth authorization code from a pasted callback URL."""

    parsed = urlparse(value.strip())
    return extract_callback_code(parsed.query, expected_state=flow.state)


class CodexOAuthClient(OAuthProviderClient):
    """Authlib-backed client for OpenAI Codex OAuth/OIDC operations."""

    def __init__(self) -> None:
        self._openid_configuration: OpenIDConfiguration | None = None
        self._jwks: KeySet | None = None

    @staticmethod
    def _oauth_client() -> AsyncOAuth2Client:
        return AsyncOAuth2Client(
            client_id=CLIENT_ID,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            token_endpoint_auth_method="none",  # noqa: S106
            trust_env=False,
        )

    def create_authorization_flow(self, *, originator: str = "koda") -> OAuthAuthorizationFlow:
        """Create an OpenAI Codex OAuth authorization URL with PKCE enabled."""

        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = create_s256_code_challenge(code_verifier)
        client = self._oauth_client()
        url, _state = client.create_authorization_url(
            AUTHORIZE_URL,
            state=state,
            nonce=nonce,
            code_challenge=code_challenge,
            code_challenge_method="S256",
            id_token_add_organizations="true",  # noqa: S106
            codex_cli_simplified_flow="true",
            originator=originator,
        )
        return OAuthAuthorizationFlow(
            url=url,
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
        )

    @staticmethod
    def _token_error(operation: str, message: str) -> OpenAICodexTokenError:
        return OpenAICodexTokenError(operation, message)

    @classmethod
    def _credential_error(cls, message: str) -> OpenAICodexTokenError:
        return cls._token_error("credential", message)

    @classmethod
    def _parse_token_response(
        cls,
        data: Mapping[str, JsonValue],
        *,
        operation: str,
    ) -> CodexTokenResponsePayload:
        try:
            return CodexTokenResponsePayload.model_validate(data)
        except ValidationError as error:
            raise cls._token_error(operation, RESPONSE_JSON_INVALID) from error

    @classmethod
    async def _get_json(cls, url: str, *, error_message: str) -> JsonValue:
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.get(url)
                response.raise_for_status()
                return cast("JsonValue", response.json())
        except (httpx.HTTPError, ValueError) as error:
            raise cls._credential_error(error_message) from error

    @classmethod
    def _wrap_oauth_error(cls, operation: str, error: Exception) -> OpenAICodexTokenError:
        return cls._token_error(operation, str(error))

    async def _fetch_token(
        self,
        code: str,
        flow: OAuthAuthorizationFlow,
    ) -> CodexTokenResponsePayload:
        try:
            async with self._oauth_client() as client:
                token = await client.fetch_token(
                    TOKEN_URL,
                    grant_type="authorization_code",
                    code=code,
                    code_verifier=flow.code_verifier,
                    redirect_uri=REDIRECT_URI,
                )
        except (OAuth2Error, httpx.HTTPError) as error:
            raise self._wrap_oauth_error("exchange", error) from error
        return self._parse_token_response(token, operation="exchange")

    async def _refresh_token(self, refresh_token: str) -> CodexTokenResponsePayload:
        try:
            async with self._oauth_client() as client:
                token = await client.refresh_token(TOKEN_URL, refresh_token=refresh_token)
        except (OAuth2Error, httpx.HTTPError) as error:
            raise self._wrap_oauth_error("refresh", error) from error
        return self._parse_token_response(token, operation="refresh")

    async def _fetch_openid_configuration(self) -> OpenIDConfiguration:
        if self._openid_configuration is not None:
            return self._openid_configuration

        data = await self._get_json(
            OIDC_DISCOVERY_URL,
            error_message=OPENID_CONFIGURATION_FETCH_FAILED,
        )
        try:
            configuration = OpenIDConfiguration.model_validate(data)
        except ValidationError as error:
            raise self._credential_error(OPENID_CONFIGURATION_INVALID) from error

        if configuration.issuer != EXPECTED_DISCOVERY_ISSUER:
            raise self._credential_error(OPENID_ISSUER_MISMATCH)

        self._openid_configuration = configuration
        return configuration

    @classmethod
    def _parse_jwks(cls, data: JsonValue) -> KeySet:
        try:
            jwks = JWKS.model_validate(data)
            return KeySet([import_key(key) for key in jwks.keys])
        except (JoseError, ValidationError) as error:
            raise cls._credential_error(OPENID_JWKS_INVALID) from error

    async def _fetch_jwks(self) -> KeySet:
        if self._jwks is not None:
            return self._jwks

        configuration = await self._fetch_openid_configuration()
        data = await self._get_json(
            configuration.jwks_uri,
            error_message=OPENID_JWKS_FETCH_FAILED,
        )
        self._jwks = self._parse_jwks(data)
        return self._jwks

    async def _validate_id_token(
        self,
        id_token: str,
        *,
        nonce: str | None = None,
    ) -> JsonObject:
        """Validate an OpenAI OIDC ID token and return trusted claims."""

        jwks = await self._fetch_jwks()
        try:
            token = jwt.decode(id_token, jwks, algorithms=ID_TOKEN_ALGORITHMS)
            JWTClaimsRegistry(
                iss={"essential": True, "value": EXPECTED_ID_TOKEN_ISSUER},
                aud={"essential": True, "value": CLIENT_ID},
                exp={"essential": True},
                leeway=ID_TOKEN_LEEWAY_SECONDS,
            ).validate(token.claims)
        except JoseError as error:
            raise self._credential_error(JWT_VALIDATION_FAILED) from error

        claims = token.claims
        if nonce is not None and claims.get("nonce") != nonce:
            raise self._credential_error(JWT_NONCE_MISMATCH)
        return claims

    @classmethod
    def _token_expires_at(cls, token: CodexTokenResponsePayload) -> int:
        if token.expires_at is not None:
            return token.expires_at
        if token.expires_in is not None:
            return int(time() + token.expires_in)
        raise cls._credential_error(RESPONSE_MISSING_EXPIRY_FIELD)

    def _credential_from_token(
        self,
        token: CodexTokenResponsePayload,
        claims: Mapping[str, JsonValue],
    ) -> OAuthCredential:
        """Convert an OpenAI Codex OAuth token response into persisted credentials."""

        account_id = extract_account_id(claims)
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
            expires_at=str(self._token_expires_at(token)),
            metadata={CODEX_ACCOUNT_ID_METADATA_KEY: account_id},
        )

    async def exchange_code(
        self,
        code: str,
        flow: OAuthAuthorizationFlow,
    ) -> OAuthCredential:
        """Exchange an authorization code for validated OpenAI Codex credentials."""

        log.info("codex_oauth_exchanging_code", token_url=TOKEN_URL)
        token = await self._fetch_token(code, flow)
        log.info(
            "codex_oauth_token_fetched",
            has_refresh_token=bool(token.refresh_token),
            has_expires_at=token.expires_at is not None,
            has_expires_in=token.expires_in is not None,
        )
        claims = await self._validate_id_token(token.id_token, nonce=flow.nonce)
        return self._credential_from_token(token, claims)

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        """Refresh existing OpenAI Codex OAuth credentials."""

        token = await self._refresh_token(credential.refresh_token)
        claims = await self._validate_id_token(token.id_token)
        return self._credential_from_token(token, claims)


def extract_account_id(claims: Mapping[str, JsonValue]) -> str | None:
    """Return the ChatGPT account id embedded in validated OpenAI Codex claims."""

    auth_claim = claims.get(JWT_CLAIM_PATH)
    if not isinstance(auth_claim, dict):
        return None
    account_id = auth_claim.get("chatgpt_account_id")
    return account_id if isinstance(account_id, str) and account_id else None


class OpenAICodexProviderAuth:
    """OpenAI Codex OAuth provider auth using ChatGPT subscription login."""

    id = "openai:oauth"

    def __init__(self, *, oauth_client: OAuthProviderClient) -> None:
        self._oauth_client = oauth_client

    async def _authorization_code_from_callback_or_prompt(
        self,
        flow: OAuthAuthorizationFlow,
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
                return extract_authorization_code(flow, prompt_task.result())
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

        flow = self._oauth_client.create_authorization_flow()
        log.info("codex_oauth_auth_url_generated", state=flow.state[:8] + "...")
        callbacks.on_auth_url(flow.url)
        code = await self._authorization_code_from_callback_or_prompt(flow, callbacks)
        log.info("codex_oauth_callback_received")
        return await self._oauth_client.exchange_code(code, flow)

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        """Refresh an existing OpenAI Codex OAuth credential."""

        return await self._oauth_client.refresh(credential)
