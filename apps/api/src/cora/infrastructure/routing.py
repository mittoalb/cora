"""Cross-BC route helpers and the system-principal fallback constant.

Hosts the three pieces every BC's slice routes need:

  - `get_correlation_id` — FastAPI Depends that returns the current
    request's correlation UUID derived from the active OTel span
    (or a fresh UUIDv4 when no span is active, e.g. in tests using
    the no-op tracer).
  - `get_principal_id` — FastAPI Depends that extracts the calling
    principal's UUID from the `X-Principal-Id` header (Pydantic
    UUID-validates -> 422 on malformed). When
    `Settings.require_authenticated_principal` is False (Phase 1
    dev / test default), an absent header falls back to
    `SYSTEM_PRINCIPAL_ID`. When True (production posture), an
    absent header raises HTTP 401 instead. See the "Production
    hardening conventions" section of CONTRIBUTING.md for the
    trust-the-proxy deployment requirement.
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

from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from cora.infrastructure.observability import current_correlation_id

SYSTEM_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000000")
"""Fallback principal used when no `X-Principal-Id` header is supplied.

Used only when `Settings.require_authenticated_principal` is False
(Phase 1 dev / test posture). Production deployments behind an auth
proxy set the header on every request and turn the setting on so
header-absent requests are rejected at the boundary instead of
silently running as SYSTEM. Under `TrustAuthorize` with a real
policy that doesn't permit `SYSTEM_PRINCIPAL_ID`, fallback-using
requests get 403 even with the setting off — defense in depth pinned
by `tests/contract/test_principal_header.py`.
"""


SYSTEM_HTTP_SURFACE_ID = UUID("00000000-0000-0000-0000-000000000020")
SYSTEM_MCP_STDIO_SURFACE_ID = UUID("00000000-0000-0000-0000-000000000021")
SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID = UUID("00000000-0000-0000-0000-000000000022")
"""Seeded arrival-Surface UUIDs.

These three constants are written by the
20260519200000_seed_default_surfaces_and_v2_policy.sql migration and
referenced by `cora.trust._bootstrap` (verify_bootstrap_seed_present)
and by `get_surface_id` / `get_mcp_surface_id` below.

Lives in `cora.infrastructure.routing` rather than `cora.trust._bootstrap`
so every BC's route / tool can import the resolver helpers without
violating the tach BC-isolation rule (BCs may import infrastructure
but not other BCs or `cora.api`). `cora.trust._bootstrap` re-exports
these for backward compatibility with existing trust-internal callers.
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


def _require_authenticated_principal(request: Request) -> bool:
    """Read the `require_authenticated_principal` flag off the running
    app's settings (carried on the kernel attached to `app.state.deps`).

    Lives as its own Depends so `get_principal_id` stays testable in
    isolation and so the read happens at request time (the kernel
    isn't attached to app.state until the lifespan runs).
    """
    return bool(request.app.state.deps.settings.require_authenticated_principal)


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
                "TRUSTS this header (no cryptographic verification here). "
                "Behavior when absent depends on "
                "Settings.require_authenticated_principal: False (default) "
                "falls back to SYSTEM_PRINCIPAL_ID; True returns 401."
            ),
        ),
    ] = None,
    require_authenticated: Annotated[
        bool,
        Depends(_require_authenticated_principal),
    ] = False,
) -> UUID:
    """Resolve the calling principal's id from the X-Principal-Id header.

    Trust-the-proxy extraction shape (Phase 3f). See the header
    description above for the production deployment requirement.
    Pydantic validates UUID format; malformed values surface as 422
    before this function is even called. Behavior on missing header:

      - `require_authenticated_principal=False` (Phase 1 default):
        fall back to `SYSTEM_PRINCIPAL_ID`.
      - `require_authenticated_principal=True` (production posture):
        raise HTTP 401.
    """
    if x_principal_id is None:
        if require_authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Missing X-Principal-Id header; this deployment "
                    "requires an authenticated principal."
                ),
            )
        return SYSTEM_PRINCIPAL_ID
    return x_principal_id


def get_surface_id(request: Request) -> UUID:
    """Resolve the arrival Surface for an HTTP request.

    v1: static return. Process-derived (no client-asserted header /
    query param) per Phase B Iter C-2 AH1. Phase C extends the body
    to validate the bearer token's `aud` claim against the Surface's
    expected audience before returning — `request: Request` is in
    the signature today so Phase C extends the body without changing
    the dependency API.
    """
    _ = request
    return SYSTEM_HTTP_SURFACE_ID


def get_mcp_surface_id() -> UUID:
    """Resolve the arrival Surface for an MCP tool call.

    CORA only serves MCP over streamable-http in production (per
    `cora/api/main.py` mounting `streamable_http_app()`). Stdio is
    unreachable in production. The adapter returns the streamable-
    http constant unconditionally — no `ctx` parameter needed, so
    existing MCP tool signatures don't change.

    If stdio shipping is added later, pin the surface id on a
    closure parameter at tool-registration time
    (`register(mcp, *, surface_id=...)`) rather than inspecting
    `ctx` — AH1 (no client-asserted surface) is preserved either
    way. GR3 RISK-1 + RISK-4.
    """
    return SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID


__all__ = [
    "SYSTEM_PRINCIPAL_ID",
    "ErrorResponse",
    "get_correlation_id",
    "get_principal_id",
]
