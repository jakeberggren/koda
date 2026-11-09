from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Self

if TYPE_CHECKING:
    from collections.abc import Sequence

    from koda.llm.apis import LLMApi
    from koda.llm.protocols import Credentials

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
    """One way to reach a provider: an API, an endpoint and an auth method."""

    id: str
    provider: str
    api: type[LLMApi]
    base_url: str
    auth: AuthMethod = "api-key"
    label: str | None = None
    description: str | None = None
    detail: str | None = None
    capabilities: dict[str, object] = field(default_factory=dict)

    @property
    def credential_key(self) -> str:
        """The key this connection's credential is stored under."""
        return f"{self.provider}:{self.id}"


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
    detail: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    thinking_options: tuple[ThinkingOption, ...] = ()
    thinking_budget_tokens: int | None = None
    capabilities: dict[str, object] = field(default_factory=dict)
    connections: tuple[Connection, ...] = ()

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

    def connection(self, credentials: Credentials) -> Connection:
        """The connection to use: the first with a matching credential, OAuth first.

        Falls back to the preferred connection when none has a credential.
        """
        preferred = sorted(self.connections, key=lambda connection: connection.auth != "oauth")
        for connection in preferred:
            credential = credentials.get_credential(connection.credential_key)
            if credential is not None and credential.auth_type == connection.auth:
                return connection
        return preferred[0]
