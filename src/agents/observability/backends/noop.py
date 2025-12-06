"""No-op observability implementation for testing."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from agents.observability.base import Observability, Span, Trace


class NoOpObservability(Observability):
    """No-op implementation that does nothing.

    Useful for testing or when observability is disabled.
    """

    @asynccontextmanager
    async def trace(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> AsyncIterator[Trace]:
        """Start a no-op trace.

        Args:
            name: Trace name.
            metadata: Optional metadata dictionary.
            tags: Optional list of tags.

        Yields:
            Trace object.
        """
        yield _NoOpTrace()

    @asynccontextmanager
    async def span(
        self,
        name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[Span]:
        """Start a no-op span.

        Args:
            name: Span name.
            trace_id: Optional trace ID to associate with.
            parent_span_id: Optional parent span ID.
            metadata: Optional metadata dictionary.

        Yields:
            Span object.
        """
        yield _NoOpSpan()

    def log_generation(
        self,
        input: str | list | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """No-op generation logging.

        Args:
            input: Input messages or text.
            output: Output text.
            metadata: Optional metadata dictionary.
        """
        pass

    def log_score(
        self,
        name: str = "score",
        value: float | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """No-op score logging.

        Args:
            name: Name of the score.
            value: Score value.
            metadata: Optional metadata dictionary.
        """
        pass


class _NoOpTrace:
    """No-op trace wrapper."""

    @property
    def id(self) -> str:
        """Get the trace ID."""
        return ""


class _NoOpSpan:
    """No-op span wrapper."""

    @property
    def id(self) -> str:
        """Get the span ID."""
        return ""
