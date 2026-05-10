"""BC-level bootstrap constants used by both REST and MCP surfaces.

Phase 3a runs every Trust command as a hardcoded "system" principal
under `AllowAllAuthorize` (same posture as Access today). When the
real `TrustAuthorize` adapter lands, this constant is retired in
favour of the authenticated principal surfaced through the request /
MCP context — same one-edit swap as Access's bootstrap.

Distinct module from `cora.access._bootstrap` so each BC owns its
own placeholder; cross-BC sharing happens at the infrastructure
layer (the eventual Authorize adapter), not by importing across BCs.
"""

from uuid import UUID

SYSTEM_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000000")
