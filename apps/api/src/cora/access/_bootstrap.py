"""BC-level bootstrap constants used by both REST and MCP surfaces.

Phase 1 runs every command as a hardcoded "system" actor under
`AllowAllAuthorize`. Phase 3 replaces these constants with the
authenticated actor surfaced through the Trust BC. Single home so the
swap is one edit; both `features/<slice>/route.py` and
`features/<slice>/tool.py` import from here.
"""

from uuid import UUID

SYSTEM_ACTOR_ID = UUID("00000000-0000-0000-0000-000000000000")
