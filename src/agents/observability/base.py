"""Base observability interface and abstractions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from agents.core.message import Message


class Observability(Protocol):
    """Protocol defining the observability interface.

    Any class that implements these methods will satisfy this protocol.
    Supports Langfuse, Braintrust, and other observability backends.
    """

    async def trace(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> AsyncIterator[Trace]:
        """Start a new trace (full agent run).

        Args:
            name: Name of the trace.
            metadata: Optional metadata dictionary.
            tags: Optional list of tags.

        Yields:
            Trace object.

        Example:
            async with observability.trace("my-trace") as trace:
                # Do work
                print(trace.id)
        """
        ...

    async def span(
        self,
        name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[Span]:
        """Start a new span (individual operation).

        Args:
            name: Name of the span.
            trace_id: Optional trace ID to associate with.
            parent_span_id: Optional parent span ID.
            metadata: Optional metadata dictionary.

        Yields:
            Span object.

        Example:
            async with observability.span("my-span") as span:
                # Do work
                print(span.id)
        """
        ...

    def log_generation(
        self,
        input: str | list[Message] | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a generation (input/output pair).

        Args:
            input: Input messages or text.
            output: Output text.
            metadata: Optional metadata dictionary.
        """
        ...

    def log_score(
        self,
        name: str = "score",
        value: float | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a score/metric.

        Args:
            name: Name of the score.
            value: Score value.
            metadata: Optional metadata dictionary.
        """
        ...


class Trace(Protocol):
    """Protocol for trace objects."""

    @property
    def id(self) -> str:
        """Get the trace ID."""
        ...


class Span(Protocol):
    """Protocol for span objects."""

    @property
    def id(self) -> str:
        """Get the span ID."""
        ...
