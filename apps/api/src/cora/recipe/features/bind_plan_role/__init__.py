"""Vertical slice for the `BindPlanRole` command.

Binds a Method.required_role to a specific Asset on a Plan (slice 2
of the positional role-tagging workstream). Cross-aggregate
validation: the role_name must be declared on Method.required_roles,
the Asset must be in Plan.asset_ids, the Asset must carry the role's
required Family, and the Asset's ports must cover the role's
required_ports. Strict-not-idempotent on role_name.

Module-as-namespace surface:

    from cora.recipe.features import bind_plan_role

    cmd = bind_plan_role.BindPlanRole(
        plan_id=...,
        role_name=RoleName("detector"),
        asset_id=...,
    )
    handler = bind_plan_role.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

See [[project-plan-role-bindings-design]] for the design lock and
[[project-method-required-roles-design]] for the upstream slice-1
vocabulary that this slice consumes.
"""

from cora.recipe.features.bind_plan_role import tool
from cora.recipe.features.bind_plan_role.command import BindPlanRole
from cora.recipe.features.bind_plan_role.context import BindPlanRoleContext
from cora.recipe.features.bind_plan_role.decider import decide
from cora.recipe.features.bind_plan_role.handler import Handler, bind
from cora.recipe.features.bind_plan_role.route import router

__all__ = [
    "BindPlanRole",
    "BindPlanRoleContext",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
