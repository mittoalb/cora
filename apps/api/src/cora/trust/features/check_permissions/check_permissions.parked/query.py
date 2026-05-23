"""The `CheckPermissions` query — batched probe over a Policy.

Asks "for each of these commands, does Policy P permit
`evaluated_principal_id` via `evaluated_conduit_id`?". Returns one
`PermissionCheck` per input command in input order. Probe-shape per
AuthZEN Access Evaluation API + GCP `testIamPermissions` + k8s
`SelfSubjectAccessReview` (batched variant).

See `memory/project_permissions_query_design.md` for the design lock
including the no-wildcards rule and the tristate-reserved
`decision` enum.

Field naming mirrors `evaluate_policy.EvaluatePolicy`: the
`evaluated_*` prefix disambiguates WHAT'S BEING EVALUATED from the
CALLER's `principal_id` handler kwarg.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class CheckPermissions:
    """Probe a Policy against (principal, conduit) for N commands."""

    policy_id: UUID
    evaluated_principal_id: UUID
    evaluated_conduit_id: UUID
    evaluated_commands: tuple[str, ...]
    """Ordered tuple of distinct command names to probe.

    Order preserved into the response so a UI pre-flighting N commands
    can map results positionally. Distinctness + bounds checked at the
    route / decider layer (1..50 commands, 1..128 chars each, no
    wildcards).
    """


@dataclass(frozen=True)
class PermissionCheck:
    """One probe result.

    `decision` is a string enum, not bool, to reserve space for
    `"no_opinion"` when multi-policy composition lands.
    `reason` is populated only on deny.
    """

    command: str
    decision: Literal["allow", "deny"]
    reason: str | None
