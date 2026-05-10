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


@dataclass(frozen=True)
class DefinePolicy:
    """Define a new authorization Policy for a Conduit."""

    name: str
    conduit_id: UUID
    permitted_principals: frozenset[UUID]
    permitted_commands: frozenset[str]
