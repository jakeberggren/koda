"""Braintrust observability implementation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import braintrust  # type: ignore[import-untyped]

from agents.core.message import Message
from agents.observability.base import Observability, Span, Trace


class BraintrustObservability(Observability):
    """Braintrust implementation of the Observability protocol."""

    def __init__(
        self,
        api_key: str | None = None,
        project_name: str | None = None,
    ) -> None:
        """Initialize Braintrust observability.

        Args:
            api_key: Braintrust API key.
            project_name: Optional project name.
        """
        self.api_key = api_key
        self.project_name = project_name
        if api_key:
            braintrust.login(api_key=api_key)

    @asynccontextmanager
    async def trace(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> AsyncIterator[Trace]:
        """Start a Braintrust trace.

        Args:
            name: Trace name.
            metadata: Optional metadata dictionary.
            tags: Optional list of tags.

        Yields:
            Trace object.
        """
        # Braintrust manages trace IDs internally via context
        trace = _BraintrustTrace(name, metadata, tags)
        yield trace

    @asynccontextmanager
    async def span(
        self,
        name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[Span]:
        """Start a Braintrust span.

        Args:
            name: Span name.
            trace_id: Optional trace ID to associate with.
            parent_span_id: Optional parent span ID.
            metadata: Optional metadata dictionary.

        Yields:
            Span object.
        """
        span = _BraintrustSpan(name, metadata)
        yield span

    def log_generation(
        self,
        input: str | list[Message] | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a generation to Braintrust.

        Args:
            input: Input messages or text.
            output: Output text.
            metadata: Optional metadata dictionary.
        """
        input_str = self._format_input(input)
        braintrust.log(
            inputs={"input": input_str},
            output=output,
            metadata=metadata,
        )

    def log_score(
        self,
        name: str = "score",
        value: float | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a score to Braintrust.

        Args:
            name: Name of the score.
            value: Score value.
            metadata: Optional metadata dictionary.
        """
        braintrust.log(
            scores={name: value},
            metadata=metadata,
        )

    def _format_input(self, input: str | list[Message] | None) -> str | None:
        """Format input for Braintrust.

        Args:
            input: Input to format.

        Returns:
            Formatted input string or None.
        """
        if input is None:
            return None
        if isinstance(input, str):
            return input
        if isinstance(input, list):
            return "\n".join(str(msg) for msg in input)
        return str(input)


class _BraintrustTrace:
    """Braintrust trace wrapper."""

    def __init__(
        self,
        name: str,
        metadata: dict[str, Any] | None,
        tags: list[str] | None,
    ) -> None:
        """Initialize the trace wrapper.

        Args:
            name: Trace name.
            metadata: Optional metadata dictionary.
            tags: Optional list of tags.
        """
        self.name = name
        self.metadata = metadata
        self.tags = tags
        # Braintrust manages trace IDs internally via context
        # Since we're creating a new trace, we don't have an ID yet
        # Return empty string - Braintrust will handle trace correlation
        self._id = ""

    @property
    def id(self) -> str:
        """Get the trace ID."""
        return self._id


class _BraintrustSpan:
    """Braintrust span wrapper."""

    def __init__(self, name: str, metadata: dict[str, Any] | None) -> None:
        """Initialize the span wrapper.

        Args:
            name: Span name.
            metadata: Optional metadata dictionary.
        """
        self.name = name
        self.metadata = metadata
        self._id = braintrust.current_span().id or ""

    @property
    def id(self) -> str:
        """Get the span ID."""
        return self._id
