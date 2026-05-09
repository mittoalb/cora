"""Derive the request's correlation UUID from the active OTel span.

The event-store schema persists `correlation_id` as a `uuid` column;
the rest of the codebase types it as `UUID`. With OTel as the source
of truth for "this request" identity, the trace_id (128-bit) maps
losslessly into a UUID via `UUID(int=trace_id)`. Both REST routes and
MCP tool entrypoints pull the correlation id from here, so the value
in event metadata always matches the value in distributed traces.

If no span is active (test environments using the no-op tracer, or
code paths invoked outside an instrumented entrypoint), a fresh
UUIDv4 is generated so callers always receive a well-formed UUID.
This is the documented fallback — no warning, no silent misbehavior.
"""

from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import INVALID_TRACE_ID

__all__ = ["current_correlation_id"]


def current_correlation_id() -> UUID:
    """Return a UUID derived from the current OTel trace_id, or a fresh UUID."""
    span_context = trace.get_current_span().get_span_context()
    if span_context.trace_id == INVALID_TRACE_ID:
        return uuid4()
    return UUID(int=span_context.trace_id)
