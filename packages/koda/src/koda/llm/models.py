from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Self

from koda.llm import exceptions

if TYPE_CHECKING:
    from collections.abc import Sequence

    from koda.llm.apis import LLMApi
    from koda.llm.auth.protocols import OAuthLoginCallbacks, ProviderAuth
    from koda.llm.credentials import Credentials, OAuthCredential

type ThinkingOptionId = str
type AuthMethod = Literal["api-key", "oauth"]


def resolve_thinking_mode(
    requested: ThinkingOptionId,
    supported: Sequence[ThinkingOptionId],
) -> ThinkingOptionId:
    """Resolve a requested thinking mode against ordered model-supported modes.

    The first supported mode is the model default/fallback. Models with no declared
    thinking modes fall back to explicit no-thinking.
    """
    if not supported:
        return "none"
    if requested in supported:
        return requested
    return supported[0]


@dataclass(frozen=True, slots=True)
class ThinkingOption:
    id: ThinkingOptionId
    label: str
    description: str | None = None

    @classmethod
    def none(cls) -> Self:
        """Return the explicit no-thinking option."""
        return cls(id="none", label="none")


@dataclass(frozen=True, slots=True, kw_only=True)
class Connection:
    """One way to reach a provider: an API, an endpoint, and an API key or, with ``oauth``,
    a browser login."""

    id: str
    provider: str
    api: type[LLMApi]
    base_url: str
    oauth: ProviderAuth | None = None
    label: str | None = None
    description: str | None = None
    detail: str | None = None
    capabilities: dict[str, object] = field(default_factory=dict)

    @property
    def auth(self) -> AuthMethod:
        return "oauth" if self.oauth is not None else "api-key"

    @property
    def credential_key(self) -> str:
        """The key this connection's credential is stored under."""
        return f"{self.provider}:{self.id}"

    def is_connected(self, credentials: Credentials) -> bool:
        """Whether ``credentials`` has a credential for this connection."""
        credential = credentials.get_credential(self.credential_key)
        return credential is not None and credential.auth_type == self.auth

    async def login(self, callbacks: OAuthLoginCallbacks) -> OAuthCredential:
        """Log in through the browser; ``callbacks`` open the URL and ask for anything the
        login needs."""
        if self.oauth is None:
            raise exceptions.LLMConfigurationError(f"{self.credential_key} has no browser login")
        return await self.oauth.login(callbacks)


@dataclass(frozen=True, slots=True, kw_only=True)
class Provider:
    id: str
    name: str
    description: str | None = None
    connections: tuple[Connection, ...] = ()

    def is_connected(self, credentials: Credentials) -> bool:
        """Whether any connection to the provider has its credential."""
        return any(connection.is_connected(credentials) for connection in self.connections)


@dataclass(frozen=True, slots=True, kw_only=True)
class Model:
    id: str
    name: str
    provider: str
    detail: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    thinking_options: tuple[ThinkingOption, ...] = ()
    thinking_budget_tokens: int | None = None
    capabilities: dict[str, object] = field(default_factory=dict)
    connections: tuple[Connection, ...] = ()
    """The connections that offer this model, in order of preference."""

    @property
    def effective_thinking_options(self) -> tuple[ThinkingOption, ...]:
        """Return selectable thinking options with no-thinking as the fallback."""
        return self.thinking_options or (ThinkingOption.none(),)

    @property
    def supports_thinking(self) -> bool:
        """Return whether this model supports any non-default thinking option."""
        return any(option.id != "none" for option in self.effective_thinking_options)

    def resolve_thinking_option(self, thinking_id: ThinkingOptionId) -> ThinkingOption:
        """Return the matching thinking option or the model's default option."""
        options = self.effective_thinking_options
        resolved_id = resolve_thinking_mode(thinking_id, [option.id for option in options])
        return next(option for option in options if option.id == resolved_id)

    def is_connected(self, credentials: Credentials) -> bool:
        """Whether any of this model's connections has a credential."""
        return any(connection.is_connected(credentials) for connection in self.connections)

    def connection(self, credentials: Credentials) -> Connection:
        """The connection to use: the first connected one."""
        for connection in self.connections:
            if connection.is_connected(credentials):
                return connection
        raise exceptions.LLMConfigurationError(f"Provider '{self.provider}' is not connected")
