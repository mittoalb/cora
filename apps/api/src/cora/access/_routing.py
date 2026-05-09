"""Shared route helpers for the Access BC.

Three pieces are byte-identical across `features/<slice>/route.py`:
  - the `get_correlation_id` FastAPI dependency
  - the `get_principal_id` FastAPI dependency
  - the `ErrorResponse` Pydantic body for OpenAPI documentation

Extracted here once the Access BC reached three command/query slices,
per the Rule of Three. Cross-BC extraction (to `cora/infrastructure/`)
will happen when a second BC's slices need the same helpers.

Slice routes still own their handler-fetcher (`_get_handler`) because
it pulls a per-slice field off `app.state.access` — different per slice.
"""

from uuid import UUID

from pydantic import BaseModel

from cora.access._bootstrap import SYSTEM_PRINCIPAL_ID
from cora.infrastructure.observability import current_correlation_id


class ErrorResponse(BaseModel):
    """Shared error body for OpenAPI documentation."""

    detail: str


def get_correlation_id() -> UUID:
    """Derive the request's correlation UUID from the active OTel span.

    OpenTelemetry is the source of truth for "this request" identity:
    `FastAPIInstrumentor` extracts the inbound W3C `traceparent` header
    (or starts a fresh trace when absent) and exposes the trace_id
    through the active span. `current_correlation_id` formats the
    128-bit trace_id as a UUID; if no span is active (test environments
    using the no-op tracer), it generates a fresh UUID.
    """
    return current_correlation_id()


def get_principal_id() -> UUID:
    """Resolve the calling principal's id. Phase 1: hardcoded system principal.

    Phase 3 (Trust BC) replaces this with header / token-extracted
    authenticated principals.
    """
    return SYSTEM_PRINCIPAL_ID
