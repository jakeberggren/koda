from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from koda.observability import base


class NoOpObservability(base.Observability):
    """No-op implementation that does nothing."""

    @asynccontextmanager
    async def trace(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> AsyncIterator[base.Trace]:
        yield _NoOpTrace()

    @asynccontextmanager
    async def span(
        self,
        name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[base.Span]:
        yield _NoOpSpan()

    def log_generation(
        self,
        input: str | list | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        pass

    def log_score(
        self,
        name: str = "score",
        value: float | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        pass


class _NoOpTrace:
    @property
    def id(self) -> str:
        return ""


class _NoOpSpan:
    @property
    def id(self) -> str:
        return ""
