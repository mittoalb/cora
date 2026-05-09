"""Composition wrapper that traces a command or query handler call.

`with_tracing(handler, *, command_name, bc, kind)` returns a callable
with the same signature as `handler`, wrapped in a span named
`<bc>.<kind>.<command_name>`. On exception the OTel SDK's span
context-manager `__exit__` records the exception event and sets
status ERROR with description `<ExcType>: <message>` automatically
(both behaviors are SDK defaults: `record_exception=True` and
`set_status_on_exception=True` on `start_as_current_span`). The
wrapper deliberately does NOT call `record_exception` or `set_status`
itself — doing so would either duplicate the exception event or
fight the SDK over the description.

Composition order in `wire.py` (innermost first): tracing wraps
idempotency wraps the bare handler, so cache hits, cache misses, and
domain failures all attribute to the tracing span correctly.

Span attributes use the `cora.*` namespace for project-specific
metadata (`cora.bc`, `cora.command`, `cora.query`); HTTP / DB /
messaging attributes come from the underlying instrumentations.
"""

from typing import Literal, Protocol

from opentelemetry import trace
from opentelemetry.trace import SpanKind

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

    `bc` and `command_name` are recorded as `cora.bc` and `cora.command`
    (or `cora.query` when `kind="query"`) attributes for trace-side
    filtering. The span name follows `<bc>.<kind>.<command_name>` so
    traces group naturally by bounded context in the UI.
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
        ):
            return await handler(*args, **kwargs)

    return wrapped


__all__ = ["AsyncHandler", "Kind", "with_tracing"]
