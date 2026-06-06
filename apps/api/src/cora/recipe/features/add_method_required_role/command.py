"""The `AddMethodRequiredRole` command, intent dataclass for this slice.

`method_id` is the target Method aggregate. `requirement` is the
full `RoleRequirement` VO (role_name + family_id + required_ports +
optional). The decider rejects a duplicate `role_name` (strict-not-
idempotent), a Method not in `Defined` status (mirrors the
required-roles-mutation lifecycle guard), and a missing Method
stream. See [[project-method-required-roles-design]].
"""

from dataclasses import dataclass
from uuid import UUID

from cora.recipe.aggregates.method import RoleRequirement


@dataclass(frozen=True)
class AddMethodRequiredRole:
    """Add a positional role slot to an existing Method's required_roles.

    The requirement is the full `RoleRequirement` VO (role_name +
    family_id + required_ports + optional). The decider enforces:
    role_name uniqueness within the Method (strict-not-idempotent),
    Method-must-exist, and Method-status-is-Defined.
    """

    method_id: UUID
    requirement: RoleRequirement
