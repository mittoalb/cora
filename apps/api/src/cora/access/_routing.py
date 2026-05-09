"""Shared route helpers for the Access BC.

Three pieces are byte-identical across `features/<slice>/route.py`:
  - the `_get_correlation_id` FastAPI dependency
  - the `_get_principal_id` FastAPI dependency
  - the `ErrorResponse` Pydantic body for OpenAPI documentation

Extracted here once the Access BC reached three command/query slices,
per the Rule of Three. Cross-BC extraction (to `cora/infrastructure/`)
will happen when a second BC's slices need the same helpers.

Slice routes still own their handler-fetcher (`_get_handler`) because
it pulls a per-slice field off `app.state.access` — different per slice.
"""

from uuid import UUID

from asgi_correlation_id import correlation_id
from pydantic import BaseModel

from cora.access._bootstrap import SYSTEM_PRINCIPAL_ID


class ErrorResponse(BaseModel):
    """Shared error body for OpenAPI documentation."""

    detail: str


def get_correlation_id() -> UUID:
    """Pull the request correlation id from asgi-correlation-id contextvar.

    The middleware is configured (in `cora.api.main`) with a UUID-only
    validator, so the contextvar is always set to a valid UUID string
    by the time this dependency runs.
    """
    raw = correlation_id.get()
    assert raw is not None, "CorrelationIdMiddleware did not set correlation_id"
    return UUID(raw)


def get_principal_id() -> UUID:
    """Resolve the calling principal's id. Phase 1: hardcoded system principal.

    Phase 3 (Trust BC) replaces this with header / token-extracted
    authenticated principals.
    """
    return SYSTEM_PRINCIPAL_ID
