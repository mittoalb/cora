"""Composition wrapper that traces a command or query handler call.

`with_tracing(handler, *, command_name, kind)` returns a callable
with the same signature as `handler`, wrapped in a span named
`<bc>.<command|query>.<command_name>` (the bc is encoded via the
caller-supplied `command_name`'s first segment, see usage). On
exception the span records the exception and sets status ERROR.

Composition order in `wire.py` (innermost first): tracing wraps
idempotency wraps the bare handler, so the cache hit / cache miss /
domain failure all attribute to the tracing span correctly.

Span attributes use the `cora.*` namespace for project-specific
metadata (`cora.bc`, `cora.command`, `cora.query`); HTTP / DB /
messaging attributes come from the underlying instrumentations.
"""

from typing import Literal, Protocol

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

Kind = Literal["command", "query"]

_tracer = trace.get_tracer("cora.access")


class AsyncHandler[**P, R](Protocol):
    """Structural type for any async callable.

    Defined as a Protocol with `async def __call__` so the wrapped
    handler returned by `with_tracing` is assignable to slice handler
    Protocols (`register_actor.IdempotentHandler` et al.), which are
    themselves `async def __call__` Protocols. Typing with
    `Callable[P, Coroutine[...]]` doesn't work here: pyright resolves
    `async def __call__` Protocol methods to `CoroutineType`-returning,
    which `Coroutine` is not assignable to even though the runtime
    objects are interchangeable.
    """

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


def with_tracing[**P, R](
    handler: AsyncHandler[P, R],
    *,
    command_name: str,
    bc: str,
    kind: Kind = "command",
) -> AsyncHandler[P, R]:
    """Wrap an async handler with an OTel span around the call.

    `command_name` and `bc` are recorded as `cora.command` (or
    `cora.query`) and `cora.bc` attributes for trace-side filtering.
    The span name follows `<bc>.<kind>.<command_name>` so traces
    group naturally by bounded context in the UI.
    """
    span_name = f"{bc}.{kind}.{command_name}"
    name_attr = f"cora.{kind}"

    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        with _tracer.start_as_current_span(
            span_name,
            kind=SpanKind.INTERNAL,
            attributes={
                "cora.bc": bc,
                name_attr: command_name,
            },
        ) as span:
            try:
                return await handler(*args, **kwargs)
            except Exception as exc:
                # record_exception adds the exception as a span event;
                # set_status marks the span itself as failed so it shows
                # up red in the UI. Both are needed (record_exception
                # alone leaves status=UNSET which most UIs render green).
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                raise

    return wrapped


__all__ = ["AsyncHandler", "Kind", "with_tracing"]
