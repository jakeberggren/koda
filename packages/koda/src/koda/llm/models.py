from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Self

from koda.llm import exceptions

if TYPE_CHECKING:
    from koda.llm.apis import LLMApi
    from koda.llm.auth.protocols import OAuthLoginCallbacks, ProviderAuth
    from koda.llm.credentials import OAuthCredential

type ThinkingOptionId = str
type AuthMethod = Literal["api-key", "oauth"]


@dataclass(frozen=True, slots=True)
class ThinkingOption:
    id: ThinkingOptionId
    label: str
    description: str | None = None

    @classmethod
    def none(cls) -> Self:
        """Return the explicit no-thinking option."""
        return cls(id="none", label="none")


@dataclass(frozen=True, slots=True)
class Thinking:
    """The thinking levels a model offers, in order; the first is its default. Never
    empty: a model that can't think offers only "none"."""

    options: tuple[ThinkingOption, ...] = (ThinkingOption.none(),)

    def __post_init__(self) -> None:
        if not self.options:
            raise ValueError("Thinking needs at least one option")

    @property
    def supported(self) -> bool:
        """Whether there's a level besides "none" to choose."""
        return any(option.id != "none" for option in self.options)

    def resolve(self, option_id: ThinkingOptionId) -> ThinkingOption:
        """The option with ``option_id``, or the default when there's none such."""
        return next((option for option in self.options if option.id == option_id), self.options[0])

    def next(self, current: ThinkingOptionId) -> ThinkingOptionId | None:
        """The next level after ``current``, wrapping around; None with nothing to choose."""
        if not self.supported:
            return None
        index = self.options.index(self.resolve(current))
        return self.options[(index + 1) % len(self.options)].id


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
    detail: str = ""
    capabilities: dict[str, object] = field(default_factory=dict)

    @property
    def auth(self) -> AuthMethod:
        return "oauth" if self.oauth is not None else "api-key"

    @property
    def credential_key(self) -> str:
        """The key this connection's credential is stored under."""
        return f"{self.provider}:{self.id}"

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


@dataclass(frozen=True, slots=True, kw_only=True)
class Model:
    id: str
    name: str
    provider: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    thinking: Thinking = Thinking()
    capabilities: dict[str, object] = field(default_factory=dict)
    connections: tuple[Connection, ...] = ()
    """The connections that offer this model, in order of preference."""
