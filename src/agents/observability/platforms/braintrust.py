from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import braintrust

from agents.core.message import Message
from agents.observability.base import Observability, Span, Trace


class BraintrustObservability(Observability):
    def __init__(
        self,
        api_key: str | None = None,
        project_name: str | None = None,
    ) -> None:
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
        span = _BraintrustSpan(name, metadata)
        yield span

    def log_generation(
        self,
        input: str | list[Message] | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
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
        braintrust.log(
            scores={name: value},
            metadata=metadata,
        )

    def _format_input(self, input: str | list[Message] | None) -> str | None:
        if input is None:
            return None
        if isinstance(input, str):
            return input
        if isinstance(input, list):
            return "\n".join(str(msg) for msg in input)
        return str(input)


class _BraintrustTrace:
    def __init__(
        self,
        name: str,
        metadata: dict[str, Any] | None,
        tags: list[str] | None,
    ) -> None:
        self.name = name
        self.metadata = metadata
        self.tags = tags
        # Braintrust manages trace IDs internally via context
        # Since we're creating a new trace, we don't have an ID yet
        # Return empty string - Braintrust will handle trace correlation
        self._id = ""

    @property
    def id(self) -> str:
        return self._id


class _BraintrustSpan:
    def __init__(self, name: str, metadata: dict[str, Any] | None) -> None:
        self.name = name
        self.metadata = metadata
        self._id = braintrust.current_span().id or ""

    @property
    def id(self) -> str:
        return self._id
