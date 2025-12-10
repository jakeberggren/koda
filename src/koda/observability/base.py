from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from koda.core import message


class Observability(Protocol):
    async def trace(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> AsyncIterator[Trace]: ...

    async def span(
        self,
        name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[Span]: ...

    def log_generation(
        self,
        input: str | list[message.Message] | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    def log_score(
        self,
        name: str = "score",
        value: float | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...


class Trace(Protocol):
    @property
    def id(self) -> str: ...


class Span(Protocol):
    @property
    def id(self) -> str: ...
