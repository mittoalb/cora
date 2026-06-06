"""The `RemoveMethodRequiredRole` command, intent dataclass for this slice.

`method_id` is the target Method aggregate. `role_name` is the
Method-local positional role label whose declaration is being
removed; identity within `Method.required_roles` is keyed on
role_name. The decider rejects an unknown role_name (strict-not-
idempotent), a Method not in `Defined` status (mirrors the add-side
lifecycle guard), and a missing Method stream. See
[[project-method-required-roles-design]].
"""

from dataclasses import dataclass
from uuid import UUID

from cora.recipe.aggregates.method import RoleName


@dataclass(frozen=True)
class RemoveMethodRequiredRole:
    """Remove a positional role slot from an existing Method's required_roles.

    The role is identified by `role_name` alone (the structural
    identity within the Method scope); the decider rejects an
    unknown role_name. Lifecycle restricted to `Defined` (symmetric
    with `add_method_required_role`).
    """

    method_id: UUID
    role_name: RoleName
