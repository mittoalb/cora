"""The `DefinePolicy` command — intent dataclass for this slice.

Carries what the caller controls: the policy's display name, the
governed conduit's id, and the two permission sets.

`permitted_principals` and `permitted_commands` are `frozenset` so
the command is hashable + deduplicated by construction. The route
layer accepts JSON arrays and converts before constructing this
command. Empty sets are allowed (deny-all policies); see the
Policy aggregate's `state.py` docstring for the rationale.

`conduit_id` is stored as a bare UUID without verifying the
referenced Conduit exists — same eventual-consistency stance as
`Conduit.source_zone_id` / `target_zone_id` in 3b.
"""

from dataclasses import dataclass
from uuid import UUID

_NIL_SENTINEL_ID = UUID(int=0)


@dataclass(frozen=True)
class DefinePolicy:
    """Define a new authorization Policy for a Conduit + Surface pair.

    `surface_id` (Phase B Iter B): defaults to nil so existing
    callers (V1 bootstrap-shape tests + pre-Iter-C handlers) don't
    need to pass it. V2 bootstrap policy (Iter C) sets a real
    SYSTEM_HTTP_SURFACE_ID.
    """

    name: str
    conduit_id: UUID
    permitted_principals: frozenset[UUID]
    permitted_commands: frozenset[str]
    surface_id: UUID = _NIL_SENTINEL_ID
