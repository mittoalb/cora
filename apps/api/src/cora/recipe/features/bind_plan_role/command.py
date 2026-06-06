"""The `BindPlanRole` command, intent dataclass for this slice.

`plan_id` is the target Plan. `role_name` identifies which of the
Plan's bound Method's required_roles is being filled (Method-local
free string; validated against Method.required_roles at decide time).
`asset_id` is the Asset filling the role; must be in Plan.asset_ids.

The decider does the heavy lifting: validates the role_name is
declared on the Method, the Asset is bound to the Plan, the bound
Asset carries the role's required Family, and the bound Asset's
ports cover the role's required_ports. Strict-not-idempotent on
role_name. See [[project-plan-role-bindings-design]].
"""

from dataclasses import dataclass
from uuid import UUID

from cora.recipe.aggregates.method import RoleName


@dataclass(frozen=True)
class BindPlanRole:
    """Bind a Method.required_role to a specific Asset on an existing Plan.

    The decider enforces: Plan exists + status is Defined, role_name
    declared on Method.required_roles, asset_id in Plan.asset_ids,
    Asset carries role.family_id, Asset.ports cover role.required_ports,
    role_name not already bound, no existing wire endpoint claims the
    role's required_port at a different Asset.
    """

    plan_id: UUID
    role_name: RoleName
    asset_id: UUID
