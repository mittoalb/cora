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

from typing import Annotated
from uuid import UUID

from fastapi import Header
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


def get_principal_id(
    x_principal_id: Annotated[
        UUID | None,
        Header(
            alias="X-Principal-Id",
            description=(
                "UUID of the calling principal. Production deployments MUST "
                "front the API with an auth proxy that verifies the caller's "
                "credentials, strips any client-supplied X-Principal-Id, and "
                "sets it to the verified principal UUID. The application "
                "TRUSTS this header — there is no cryptographic verification "
                "here. When absent, falls back to SYSTEM_PRINCIPAL_ID for "
                "dev / test convenience."
            ),
        ),
    ] = None,
) -> UUID:
    """Resolve the calling principal's id from the X-Principal-Id header.

    Phase 3f extraction shape: trust-the-proxy. See header docstring
    above for the production deployment requirement. Pydantic validates
    UUID format; malformed values surface as 422 before this function
    is even called. Header absent → `SYSTEM_PRINCIPAL_ID` (the Phase 1
    fallback used by tests + dev).
    """
    if x_principal_id is None:
        return SYSTEM_PRINCIPAL_ID
    return x_principal_id
