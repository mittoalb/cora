"""Composition-root surface-resolution helpers.

Lives here (not `cora/infrastructure/routing.py`) because tach
forbids `cora.infrastructure → cora.trust`, and these adapters
must import the seeded Surface UUID constants from
`cora.trust._bootstrap`.

Phase B Iter C-2a (additive — no behavioral change yet):
  - `get_surface_id` — FastAPI Depends for HTTP routes.
  - `get_mcp_surface_id` — call from inside MCP tools.

v1 both return their respective seeded Surface UUID unconditionally
(process-derived, never client-asserted per AH1). Phase C extends
`get_surface_id`'s body to validate the bearer token's `aud` claim;
the signature is already `request: Request`-typed for that.

Phase B Iter C-2 design lock + GR3 RISK-8/RISK-1/RISK-4 rationale:
memory/project_conduit_injection_design.md, Decision 8.
"""

from uuid import UUID

from fastapi import Request

from cora.trust._bootstrap import (
    SYSTEM_HTTP_SURFACE_ID,
    SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
)


def get_surface_id(request: Request) -> UUID:
    """Resolve the arrival Surface for an HTTP request.

    v1: static return. Process-derived (no client-asserted header /
    query param) per AH1. Phase C extends the body to validate the
    bearer token's `aud` claim against the Surface's expected
    audience before returning — `request: Request` is in the
    signature today so Phase C extends the body without changing
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


__all__ = ["get_mcp_surface_id", "get_surface_id"]
