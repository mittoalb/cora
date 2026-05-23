"""The `DefinePolicy` command — intent dataclass for this slice.

Carries what the caller controls: the policy's display name, the
governed conduit's id, and the two permission sets.

`permitted_principals` and `permitted_commands` are `frozenset` so
the command is hashable + deduplicated by construction. The route
layer accepts JSON arrays and converts before constructing this
command. Empty sets are allowed (deny-all policies); see the
Policy aggregate's `state.py` docstring for the rationale.

`conduit_id` is stored as a bare UUID without verifying the
referenced Conduit exists, same eventual-consistency stance as
`Conduit.source_zone_id` / `target_zone_id`.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.routing import NIL_SENTINEL_ID


@dataclass(frozen=True)
class DefinePolicy:
    """Define a new authorization Policy for a Conduit + Surface pair.

    `surface_id`: defaults to nil so existing callers (V1
    bootstrap-shape tests + pre-Surface handlers) don't need to
    pass it. V2 bootstrap policy sets a real
    SYSTEM_HTTP_SURFACE_ID.
    """

    name: str
    conduit_id: UUID
    permitted_principals: frozenset[UUID]
    permitted_commands: frozenset[str]
    surface_id: UUID = NIL_SENTINEL_ID
