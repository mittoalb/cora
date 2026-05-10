"""Cross-BC route helpers and the system-principal fallback constant.

Hosts the three pieces every BC's slice routes need:

  - `get_correlation_id` — FastAPI Depends that returns the current
    request's correlation UUID derived from the active OTel span
    (or a fresh UUIDv4 when no span is active, e.g. in tests using
    the no-op tracer).
  - `get_principal_id` — FastAPI Depends that extracts the calling
    principal's UUID from the `X-Principal-Id` header (Pydantic
    UUID-validates → 422 on malformed) and falls back to
    `SYSTEM_PRINCIPAL_ID` when the header is absent. See the
    "Production hardening conventions" section of CONTRIBUTING.md
    for the trust-the-proxy deployment requirement.
  - `ErrorResponse` — Pydantic body shape for OpenAPI documentation
    of error responses.

Also exposes `SYSTEM_PRINCIPAL_ID`, the canonical fallback principal
UUID. MCP tools import this directly to use as `principal_id` on
their handler calls (FastMCP doesn't surface request headers cleanly;
that gap is documented for a future MCP auth-flow phase).

Lives at `cora/infrastructure/` (not in any single BC) because both
BCs need byte-identical implementations and a future BC-3 will too.
Per-BC `_bootstrap.py` modules re-export `SYSTEM_PRINCIPAL_ID` from
here so existing import paths stay stable; per-BC `_routing.py`
modules are gone (their helpers moved here).

Slice routes still own their handler-fetcher (`_get_handler`)
because it pulls a per-slice field off `app.state.<bc>` — different
per slice. That's the only per-slice DI helper left.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Header
from pydantic import BaseModel

from cora.infrastructure.observability import current_correlation_id

SYSTEM_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000000")
"""Fallback principal used when no `X-Principal-Id` header is supplied.

Production deployments behind an auth proxy never see this value
(the proxy always sets the header). Dev / test / proxy-less
deployments fall back to this constant; under `TrustAuthorize` with
a real policy that doesn't permit `SYSTEM_PRINCIPAL_ID`, those
requests get 403 — fail-closed behaviour pinned by
`tests/contract/test_principal_header.py`.
"""


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

    Trust-the-proxy extraction shape (Phase 3f). See the header
    description above for the production deployment requirement.
    Pydantic validates UUID format; malformed values surface as 422
    before this function is even called. Header absent →
    `SYSTEM_PRINCIPAL_ID` (the Phase 1 fallback used by tests + dev).
    """
    if x_principal_id is None:
        return SYSTEM_PRINCIPAL_ID
    return x_principal_id


__all__ = [
    "SYSTEM_PRINCIPAL_ID",
    "ErrorResponse",
    "get_correlation_id",
    "get_principal_id",
]
