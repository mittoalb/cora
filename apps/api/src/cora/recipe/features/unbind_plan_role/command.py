"""The `UnbindPlanRole` command, intent dataclass for this slice.

`plan_id` is the target Plan. `role_name` identifies the binding
being removed (the structural identity within Plan.role_bindings).
Strict-not-idempotent: a second unbind raises rather than no-opping.
See [[project-plan-role-bindings-design]].
"""

from dataclasses import dataclass
from uuid import UUID

from cora.recipe.aggregates.method import RoleName


@dataclass(frozen=True)
class UnbindPlanRole:
    """Remove a RoleBinding from an existing Plan's role_bindings set."""

    plan_id: UUID
    role_name: RoleName
