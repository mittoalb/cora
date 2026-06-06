"""Vertical slice for the `UnbindPlanRole` command.

Removes a RoleBinding (identified by role_name) from an existing
Plan's role_bindings set; strict-not-idempotent. Mirror of
`bind_plan_role`.

See [[project-plan-role-bindings-design]] for the design lock.
"""

from cora.recipe.features.unbind_plan_role import tool
from cora.recipe.features.unbind_plan_role.command import UnbindPlanRole
from cora.recipe.features.unbind_plan_role.decider import decide
from cora.recipe.features.unbind_plan_role.handler import Handler, bind
from cora.recipe.features.unbind_plan_role.route import router

__all__ = [
    "Handler",
    "UnbindPlanRole",
    "bind",
    "decide",
    "router",
    "tool",
]
