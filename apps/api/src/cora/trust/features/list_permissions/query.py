"""The `ListPermissions` query — enumerate a Policy's permitted commands for a principal.

Asks "given Policy P, what commands can `evaluated_principal_id`
execute via `evaluated_conduit_id`?". Returns a sorted list of
permitted command names, plus an `incomplete: bool` flag (always
False at v1; required from day 1 per the design lock anti-hook
(future ABAC policies may make enumeration lossy).

Field naming mirrors `evaluate_policy.EvaluatePolicy` (the
`evaluated_*` prefix disambiguates from the caller's `principal_id`
handler kwarg).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListPermissions:
    """Enumerate a Policy's permitted commands for (principal, conduit)."""

    policy_id: UUID
    evaluated_principal_id: UUID
    evaluated_conduit_id: UUID


@dataclass(frozen=True)
class PermissionListing:
    """The enumerate result.

    `permitted_commands` is sorted alphabetically. Returns the
    intersection of the principal's eligibility (must be in
    `policy.permitted_principals`) AND conduit match (must equal
    `policy.conduit_id`) AND the policy's permitted_commands. If
    either eligibility check fails, returns the empty list.

    `incomplete: bool` is always False at v1; required for forward
    compat with ABAC/conditional policies.
    """

    policy_id: UUID
    evaluated_principal_id: UUID
    evaluated_conduit_id: UUID
    permitted_commands: list[str]
    incomplete: bool
