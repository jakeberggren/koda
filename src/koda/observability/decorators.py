from __future__ import annotations

import functools
from collections.abc import AsyncIterator, Awaitable, Callable
from inspect import isasyncgenfunction
from typing import Any, TypeVar, cast

from koda.observability import base

T = TypeVar("T")


def observable_trace(
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    observability_attr: str = "observability",
):
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        trace_name = (
            name
            or f"{getattr(func, '__module__', 'unknown')}.{
                getattr(func, '__qualname__', getattr(func, '__name__', 'unknown'))
            }"
        )

        @functools.wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> T:
            observability: base.Observability | None = getattr(self, observability_attr, None)

            if observability is None:
                return await func(self, *args, **kwargs)

            async with observability.trace(trace_name, metadata=metadata, tags=tags):
                return await func(self, *args, **kwargs)

        return wrapper

    return decorator


def observable_span(
    name: str | None = None,
    metadata: dict[str, Any] | None = None,
    observability_attr: str = "observability",
):
    def decorator(
        func: Callable[..., Awaitable[T] | AsyncIterator[T]],
    ) -> Callable[..., Awaitable[T] | AsyncIterator[T]]:
        span_name = (
            name
            or f"{getattr(func, '__module__', 'unknown')}.{
                getattr(func, '__qualname__', getattr(func, '__name__', 'unknown'))
            }"
        )

        # Check if this is an async generator function
        if isasyncgenfunction(func):
            # Handle async generator
            @functools.wraps(func)
            async def wrapper(self, *args: Any, **kwargs: Any) -> AsyncIterator[T]:
                observability: base.Observability | None = getattr(self, observability_attr, None)

                if observability is None:
                    # Type narrowing: we know func is an async generator here
                    gen = cast(Callable[..., AsyncIterator[T]], func)(self, *args, **kwargs)
                    async for item in gen:
                        yield item
                    return

                async with observability.span(span_name, metadata=metadata):
                    # Type narrowing: we know func is an async generator here
                    gen = cast(Callable[..., AsyncIterator[T]], func)(self, *args, **kwargs)
                    async for item in gen:
                        yield item

        else:
            # Handle regular async function
            @functools.wraps(func)
            async def wrapper(self, *args: Any, **kwargs: Any) -> T:
                observability: base.Observability | None = getattr(self, observability_attr, None)

                if observability is None:
                    # Type narrowing: we know func is a regular async function here
                    return await cast(Callable[..., Awaitable[T]], func)(self, *args, **kwargs)

                async with observability.span(span_name, metadata=metadata):
                    # Type narrowing: we know func is a regular async function here
                    cast_func = cast(Callable[..., Awaitable[T]], func)
                    return await cast_func(self, *args, **kwargs)

        return wrapper

    return decorator


def observable_generation(
    input_arg: str | int = 0,
    output_arg: str | int | None = None,
    metadata: dict[str, Any] | None = None,
    observability_attr: str = "observability",
):
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(self, *args: Any, **kwargs: Any) -> T:
            observability: base.Observability | None = getattr(self, observability_attr, None)

            # Extract input
            if isinstance(input_arg, int):
                input_value = args[input_arg] if input_arg < len(args) else None
            else:
                input_value = kwargs.get(input_arg)

            # Call the function
            result = await func(self, *args, **kwargs)

            # Log generation if observability is available
            if observability is not None:
                output_value = result
                if output_arg is not None:
                    if isinstance(output_arg, int):
                        output_value = args[output_arg] if output_arg < len(args) else None
                    else:
                        output_value = kwargs.get(output_arg)

                observability.log_generation(
                    input=input_value,
                    output=output_value,
                    metadata=metadata,
                )

            return result

        return wrapper

    return decorator


def observable(
    trace_name: str | None = None,
    span_name: str | None = None,
    log_generation: bool = False,
    input_arg: str | int = 0,
    metadata: dict[str, Any] | None = None,
    observability_attr: str = "observability",
):
    def decorator(
        func: Callable[..., Awaitable[T] | AsyncIterator[T]],
    ) -> Callable[..., Awaitable[T] | AsyncIterator[T]]:
        # Check if this is an async generator function
        if isasyncgenfunction(func):
            # Handle async generator
            @functools.wraps(func)
            async def wrapper(self, *args: Any, **kwargs: Any) -> AsyncIterator[T]:
                observability: base.Observability | None = getattr(self, observability_attr, None)

                if observability is None:
                    # Type narrowing: we know func is an async generator here
                    gen = cast(Callable[..., AsyncIterator[T]], func)(self, *args, **kwargs)
                    async for item in gen:
                        yield item
                    return

                trace_name_final = (
                    trace_name
                    or f"{getattr(func, '__module__', 'unknown')}.{
                        getattr(func, '__qualname__', getattr(func, '__name__', 'unknown'))
                    }"
                )
                span_name_final = span_name or trace_name_final

                async with observability.trace(trace_name_final, metadata=metadata):
                    async with observability.span(span_name_final, metadata=metadata):
                        # Extract input if logging generation
                        input_value = None
                        if log_generation:
                            if isinstance(input_arg, int):
                                input_value = args[input_arg] if input_arg < len(args) else None
                            else:
                                input_value = kwargs.get(input_arg)

                        # Collect all chunks for generation logging
                        # Type narrowing: we know func is an async generator here
                        gen = cast(Callable[..., AsyncIterator[T]], func)(self, *args, **kwargs)
                        chunks: list[T] = []
                        async for chunk in gen:
                            chunks.append(chunk)
                            yield chunk

                        # Log generation if requested
                        if log_generation and input_value is not None:
                            # For string chunks, join them; otherwise use the list
                            if chunks and isinstance(chunks[0], str):
                                result = "".join(cast(list[str], chunks)) if chunks else None
                            else:
                                result = chunks if chunks else None
                            observability.log_generation(
                                input=input_value,
                                output=result,
                                metadata=metadata,
                            )

        else:
            # Handle regular async function
            @functools.wraps(func)
            async def wrapper(self, *args: Any, **kwargs: Any) -> T:
                observability: base.Observability | None = getattr(self, observability_attr, None)

                if observability is None:
                    # Type narrowing: we know func is a regular async function here
                    return await cast(Callable[..., Awaitable[T]], func)(self, *args, **kwargs)

                trace_name_final = (
                    trace_name
                    or f"{getattr(func, '__module__', 'unknown')}.{
                        getattr(func, '__qualname__', getattr(func, '__name__', 'unknown'))
                    }"
                )
                span_name_final = span_name or trace_name_final

                async with observability.trace(trace_name_final, metadata=metadata):
                    async with observability.span(span_name_final, metadata=metadata):
                        # Extract input if logging generation
                        input_value = None
                        if log_generation:
                            if isinstance(input_arg, int):
                                input_value = args[input_arg] if input_arg < len(args) else None
                            else:
                                input_value = kwargs.get(input_arg)

                        # Call the function
                        # Type narrowing: we know func is a regular async function here
                        cast_func = cast(Callable[..., Awaitable[T]], func)
                        result = await cast_func(self, *args, **kwargs)

                        # Log generation if requested
                        if log_generation and input_value is not None:
                            observability.log_generation(
                                input=input_value,
                                output=result,
                                metadata=metadata,
                            )

                        return result

        return wrapper

    return decorator
