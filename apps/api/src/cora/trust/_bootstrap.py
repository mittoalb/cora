"""BC-level bootstrap constants used by both REST and MCP surfaces.

`SYSTEM_PRINCIPAL_ID` is the **fallback** principal used by:
  - REST routes when the `X-Principal-Id` header is absent (3f)
  - MCP tools (which don't yet extract a principal from the request;
    deferred until MCP auth flow integration lands)

Phase 3a used this as the only principal under `AllowAllAuthorize`;
Phase 3e wired `TrustAuthorize` (gates via Policy aggregate); Phase 3f
introduced header-based extraction in `_routing.py`. Production
deployments that don't run behind an auth proxy effectively still
operate as the system principal — that's a deployment
misconfiguration, not an application bug.

Distinct module from `cora.access._bootstrap` so each BC owns its
own fallback constant — keeps logs distinguishable when a request
falls back to a BC's "system" principal vs another's. Cross-BC
sharing happens at the infrastructure layer, not by importing
across BCs.
"""

from uuid import UUID

SYSTEM_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000000")
