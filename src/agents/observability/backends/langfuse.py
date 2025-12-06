"""Langfuse observability implementation for SDK v3."""

from __future__ import annotations

import traceback
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal

from langfuse import Langfuse

from agents.core.message import Message
from agents.observability.base import Observability, Span, Trace


class LangfuseObservability(Observability):
    """Langfuse implementation of the Observability protocol for SDK v3."""

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
    ) -> None:
        """Initialize Langfuse observability.

        Args:
            public_key: Langfuse public key.
            secret_key: Langfuse secret key.
            host: Optional custom Langfuse host.
        """
        self.client: Langfuse = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )

    @asynccontextmanager
    async def trace(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> AsyncIterator[Trace]:
        """Start a Langfuse trace.

        Args:
            name: Trace name.
            metadata: Optional metadata dictionary.
            tags: Optional list of tags.

        Yields:
            Trace object.
        """
        with self.client.start_as_current_observation(
            as_type="span",
            name=name,
            metadata=metadata,
        ) as span_obj:
            # Update trace-level attributes if tags provided
            if tags:
                span_obj.update_trace(tags=tags)

            trace = _LangfuseTrace(span_obj)
            print(f"[Langfuse] Trace created with ID: {trace.id}")  # DEBUG
            yield trace

        print(f"[Langfuse] Flushing trace: {name}")  # DEBUG
        self.client.flush()

    @asynccontextmanager
    async def span(
        self,
        name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[Span]:
        """Start a Langfuse span.

        Args:
            name: Span name.
            trace_id: Optional trace ID to associate with (not used in v3).
            parent_span_id: Optional parent span ID (not used in v3).
            metadata: Optional metadata dictionary.

        Yields:
            Span object.
        """
        with self.client.start_as_current_observation(
            as_type="span",
            name=name,
            metadata=metadata,
        ) as span_obj:
            span = _LangfuseSpan(span_obj)
            yield span

        self.client.flush()

    def log_generation(
        self,
        input: str | list[Message] | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
        name: str = "generation",
        model: str | None = None,
    ) -> None:
        """Log a generation to Langfuse.

        Args:
            input: Input messages or text.
            output: Output text.
            metadata: Optional metadata dictionary.
            name: Name of the generation.
            model: Optional model name.
        """
        # TODO: What does this actually do?

        input_str = self._format_input(input)
        try:
            # In v3, we use start_as_current_observation to create a generation
            # This relies on OTEL context propagation from parent trace/span
            with self.client.start_as_current_observation(
                as_type="generation",
                name=name,
                input=input_str,
                output=output,
                metadata=metadata,
                model=model,
            ):
                pass
        except Exception:
            traceback.print_exc()
        finally:
            self.client.flush()

    def log_score(
        self,
        name: str = "score",
        value: float | int | None = None,
        metadata: Any | None = None,
        trace_id: str | None = None,
        observation_id: str | None = None,
        data_type: Literal["NUMERIC", "BOOLEAN"] | None = None,
    ) -> None:
        """Log a score to Langfuse.

        Args:
            name: Name of the score.
            value: Score value (numeric).
            trace_id: Optional trace ID to associate with.
            observation_id: Optional observation ID to associate with.
            data_type: Optional data type ('NUMERIC' or 'BOOLEAN').
            comment: Optional comment for the score.
            metadata: Optional metadata (any type).
        """
        self.client.create_score(
            name=name,
            value=value or 0,
            trace_id=trace_id,
            observation_id=observation_id,
            data_type=data_type,
            metadata=metadata,
        )
        self.client.flush()

    def _format_input(self, input: str | list[Message] | None) -> str | dict | list | None:
        """Format input for Langfuse.

        Args:
            input: Input to format.

        Returns:
            Formatted input string, dict, list, or None.
        """
        if input is None:
            return None
        if isinstance(input, str):
            return input
        if isinstance(input, list):
            # For messages, try to format as list of dicts
            formatted = []
            for msg in input:
                try:
                    # If it has a dict() method (Pydantic models), use it
                    if hasattr(msg, "model_dump"):
                        formatted.append(msg.model_dump())
                    elif hasattr(msg, "dict"):
                        formatted.append(msg.dict())
                    else:
                        # Otherwise convert to string
                        formatted.append({"content": str(msg)})
                except Exception:
                    formatted.append({"content": str(msg)})
            return formatted if formatted else "\n".join(str(msg) for msg in input)
        return str(input)


class _LangfuseTrace:
    """Langfuse trace wrapper for v3."""

    def __init__(self, span: Any) -> None:
        """Initialize the trace wrapper.

        Args:
            span: Langfuse span object (root span represents trace).
        """
        self._span = span

    @property
    def id(self) -> str:
        """Get the trace ID."""
        # In v3, the trace ID is available via the trace_id attribute
        try:
            return getattr(self._span, "trace_id", "")
        except Exception:
            return ""


class _LangfuseSpan:
    """Langfuse span wrapper for v3."""

    def __init__(self, span: Any) -> None:
        """Initialize the span wrapper.

        Args:
            span: Langfuse span object.
        """
        self._span = span

    @property
    def id(self) -> str:
        """Get the span ID."""
        try:
            # Try different possible attributes
            if hasattr(self._span, "id"):
                return self._span.id
            elif hasattr(self._span, "observation_id"):
                return self._span.observation_id
            else:
                return ""
        except Exception:
            return ""
