"""BC-level bootstrap constants used by both REST and MCP surfaces.

`SYSTEM_PRINCIPAL_ID` is the **fallback** principal used by:
  - REST routes when the `X-Principal-Id` header is absent (3f)
  - MCP tools (which don't yet extract a principal from the request;
    deferred until MCP auth flow integration lands)

Phase 1 used this as the only principal under `AllowAllAuthorize`;
Phase 3f introduced header-based extraction (trust-the-proxy pattern,
documented in `_routing.py:get_principal_id`). Production deployments
that don't run behind an auth proxy effectively still operate as the
system principal — that's a deployment misconfiguration, not an
application bug.

`SYSTEM_PRINCIPAL_ID` (not `SYSTEM_ACTOR_ID`) because the constant
identifies the invoker, not an Actor-aggregate id. A principal might
be a service account, MCP-client cert, etc., and not necessarily map
to an Actor aggregate.
"""

from uuid import UUID

SYSTEM_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000000")
