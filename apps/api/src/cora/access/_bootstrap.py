"""BC-level bootstrap constants used by both REST and MCP surfaces.

Phase 1 runs every command as a hardcoded "system" principal under
`AllowAllAuthorize`. Phase 3 replaces these constants with the
authenticated principal surfaced through the Trust BC. Single home so
the swap is one edit; both `features/<slice>/route.py` and
`features/<slice>/tool.py` import from here.

`SYSTEM_PRINCIPAL_ID` (not `SYSTEM_ACTOR_ID`) because the constant
identifies the invoker, not an Actor-aggregate id. In Phase 3+ a
principal might be a service account, MCP-client cert, etc., and not
necessarily map to an Actor aggregate.
"""

from uuid import UUID

SYSTEM_PRINCIPAL_ID = UUID("00000000-0000-0000-0000-000000000000")
