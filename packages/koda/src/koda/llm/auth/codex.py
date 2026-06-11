from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from time import time
from typing import TYPE_CHECKING, Annotated, cast

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.base import OAuth2Error
from authlib.oauth2.client import OAuth2Client
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet, import_key
from joserfc.jwt import JWTClaimsRegistry
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from koda.llm.auth.browser import (
    AuthorizationRequest,
    LoopbackRedirect,
    complete_browser_authorization,
)
from koda.llm.auth.exceptions import OpenAICodexAccountMissingError, OpenAICodexTokenError
from koda.llm.auth.protocols import OAuthLoginCallbacks
from koda_common.logging import get_logger
from koda_common.settings.credentials import OAuthCredential

if TYPE_CHECKING:
    from collections.abc import Mapping

log = get_logger(__name__)

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type JwkDict = dict[str, str | list[str]]
type BrowserAuthorizer = Callable[[AuthorizationRequest, OAuthLoginCallbacks], Awaitable[str]]

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"  # noqa: S105
JWKS_URL = "https://auth.openai.com/.well-known/jwks.json"
EXPECTED_ID_TOKEN_ISSUER = "https://auth.openai.com"  # noqa: S105
ID_TOKEN_ALGORITHMS = ["RS256", "PS256"]
ID_TOKEN_LEEWAY_SECONDS = 60
REDIRECT_URI = "http://localhost:1455/auth/callback"
REDIRECT = LoopbackRedirect(host="127.0.0.1", port=1455, path="/auth/callback")
SCOPE = "openid profile email offline_access api.connectors.read api.connectors.invoke"
JWT_CLAIM_PATH = "https://api.openai.com/auth"
ACCOUNT_ID_METADATA_KEY = "chatgpt_account_id"
MANUAL_CODE_PROMPT = "Paste the full localhost callback URL from your browser here after login."


class _TokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: Annotated[StrictStr, Field(min_length=1)]
    expires_at: StrictInt | None = None
    expires_in: StrictInt | None = None


class _LoginTokenResponse(_TokenResponse):
    refresh_token: Annotated[StrictStr, Field(min_length=1)]
    id_token: Annotated[StrictStr, Field(min_length=1)]


class _RefreshTokenResponse(_TokenResponse):
    refresh_token: Annotated[StrictStr, Field(min_length=1)] | None = None
    id_token: Annotated[StrictStr, Field(min_length=1)] | None = None


class _JWKS(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keys: Annotated[list[JwkDict], Field(min_length=1)]


def _expires_at(token: _TokenResponse) -> str:
    if token.expires_at is not None:
        return str(token.expires_at)
    if token.expires_in is not None:
        return str(int(time() + token.expires_in))
    raise OpenAICodexTokenError("credential", "response missing expiry field")


def _account_id(claims: Mapping[str, JsonValue]) -> str:
    auth_claim = claims.get(JWT_CLAIM_PATH)
    account_id = auth_claim.get(ACCOUNT_ID_METADATA_KEY) if isinstance(auth_claim, dict) else None
    if not isinstance(account_id, str) or not account_id:
        raise OpenAICodexAccountMissingError
    return account_id


def _id_token_claims_registry() -> JWTClaimsRegistry:
    return JWTClaimsRegistry(
        iss={"essential": True, "value": EXPECTED_ID_TOKEN_ISSUER},
        aud={"essential": True, "value": CLIENT_ID},
        sub={"essential": True},
        exp={"essential": True},
        iat={"essential": True},
        leeway=ID_TOKEN_LEEWAY_SECONDS,
    )


def create_authorization_request(*, originator: str = "koda") -> AuthorizationRequest:
    """Create the OpenAI Codex authorization URL and PKCE state."""

    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    code_verifier = secrets.token_urlsafe(64)

    client = OAuth2Client(
        None,
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        code_challenge_method="S256",
    )
    url, _ = client.create_authorization_url(
        AUTHORIZE_URL,
        state=state,
        code_verifier=code_verifier,
        nonce=nonce,
        id_token_add_organizations="true",  # noqa: S106
        codex_cli_simplified_flow="true",
        originator=originator,
    )
    return AuthorizationRequest(
        url=url,
        state=state,
        nonce=nonce,
        code_verifier=code_verifier,
    )


async def _authorize_in_browser(
    request: AuthorizationRequest,
    callbacks: OAuthLoginCallbacks,
) -> str:
    return await complete_browser_authorization(
        request,
        callbacks,
        redirect=REDIRECT,
        prompt=MANUAL_CODE_PROMPT,
    )


class OpenAICodexAuth:
    """OpenAI Codex OAuth provider using ChatGPT subscription login."""

    id = "openai:oauth"

    def __init__(
        self,
        *,
        browser_authorizer: BrowserAuthorizer = _authorize_in_browser,
        oauth_transport: httpx.AsyncBaseTransport | None = None,
        jwks_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._browser_authorizer = browser_authorizer
        self._oauth_transport = oauth_transport
        self._jwks_transport = jwks_transport
        self._cached_jwks: KeySet | None = None

    def _token_client(self) -> AsyncOAuth2Client:
        return AsyncOAuth2Client(
            client_id=CLIENT_ID,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            token_endpoint_auth_method="none",  # noqa: S106
            trust_env=False,
            transport=self._oauth_transport,
        )

    def _validate_model[T: BaseModel](
        self,
        operation: str,
        model: type[T],
        data: object,
        message: str = "response JSON was invalid",
    ) -> T:
        try:
            return model.model_validate(data)
        except ValidationError as e:
            raise OpenAICodexTokenError(operation, message) from e

    async def _request_token[T: BaseModel](
        self,
        operation: str,
        model: type[T],
        request: Callable[[AsyncOAuth2Client], Awaitable[object]],
    ) -> T:
        try:
            async with self._token_client() as client:
                token = await request(client)
        except (OAuth2Error, httpx.HTTPError) as e:
            raise OpenAICodexTokenError(operation, str(e)) from e
        return self._validate_model(operation, model, token)

    async def _exchange_code(
        self,
        code: str,
        request: AuthorizationRequest,
    ) -> _LoginTokenResponse:
        return await self._request_token(
            "exchange",
            _LoginTokenResponse,
            lambda client: client.fetch_token(
                TOKEN_URL,
                grant_type="authorization_code",
                code=code,
                code_verifier=request.code_verifier,
                redirect_uri=REDIRECT_URI,
            ),
        )

    async def _request_refresh(self, refresh_token: str) -> _RefreshTokenResponse:
        return await self._request_token(
            "refresh",
            _RefreshTokenResponse,
            lambda client: client.refresh_token(
                TOKEN_URL,
                refresh_token=refresh_token,
            ),
        )

    async def _jwks(self) -> KeySet:
        if self._cached_jwks is not None:
            return self._cached_jwks

        try:
            async with httpx.AsyncClient(trust_env=False, transport=self._jwks_transport) as client:
                response = await client.get(JWKS_URL)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OpenAICodexTokenError("credential", "openid jwks fetch failed") from error
        jwks = self._validate_model("credential", _JWKS, data, "openid jwks was invalid")
        try:
            self._cached_jwks = KeySet([import_key(key) for key in jwks.keys])
        except JoseError as error:
            raise OpenAICodexTokenError("credential", "openid jwks was invalid") from error
        return self._cached_jwks

    async def _decode_id_token(self, id_token: str) -> JsonObject:
        try:
            token = jwt.decode(
                id_token,
                await self._jwks(),
                algorithms=ID_TOKEN_ALGORITHMS,
            )
            _id_token_claims_registry().validate(token.claims)
        except JoseError as error:
            raise OpenAICodexTokenError("credential", "id_token validation failed") from error
        return cast("JsonObject", token.claims)

    async def _validate_id_token(
        self,
        id_token: str,
        *,
        nonce: str | None = None,
    ) -> JsonObject:
        claims = await self._decode_id_token(id_token)
        if nonce is not None and claims.get("nonce") != nonce:
            raise OpenAICodexTokenError("credential", "id_token nonce mismatch")
        return claims

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
        """Run the OpenAI Codex browser login flow."""

        request = create_authorization_request()
        log.info("codex_oauth_auth_url_generated", state=request.state[:8] + "...")
        code = await self._browser_authorizer(request, callbacks)
        token = await self._exchange_code(code, request)
        claims = await self._validate_id_token(token.id_token, nonce=request.nonce)
        return OAuthCredential(
            type="oauth",
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=_expires_at(token),
            metadata={ACCOUNT_ID_METADATA_KEY: _account_id(claims)},
        )

    async def refresh(self, credential: OAuthCredential) -> OAuthCredential:
        """Refresh an existing OpenAI Codex OAuth credential."""

        token = await self._request_refresh(credential.refresh_token)
        metadata = dict(credential.metadata)
        if token.id_token is not None:
            claims = await self._validate_id_token(token.id_token)
            metadata[ACCOUNT_ID_METADATA_KEY] = _account_id(claims)
        return OAuthCredential(
            type="oauth",
            access_token=token.access_token,
            refresh_token=token.refresh_token or credential.refresh_token,
            expires_at=_expires_at(token),
            metadata=metadata,
        )
