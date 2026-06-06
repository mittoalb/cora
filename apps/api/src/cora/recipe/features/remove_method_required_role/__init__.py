"""Vertical slice for the `RemoveMethodRequiredRole` command.

Removes a single positional role slot (identified by role_name)
from an existing Method's required_roles set; strict-not-idempotent:
an unknown role_name surfaces as 404 rather than silent no-op.
Mirror of `add_method_required_role`; the lifecycle guard
(`MethodCannotMutateRequiredRolesError`) is shared because the
guard is symmetric.

Module-as-namespace surface:

    from cora.recipe.features import remove_method_required_role

    cmd = remove_method_required_role.RemoveMethodRequiredRole(
        method_id=...,
        role_name=RoleName("detector"),
    )
    handler = remove_method_required_role.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

See [[project-method-required-roles-design]] for the full design
lock and [[project-equipment-isa-gap-research]] for the Function-
aspect gap context.
"""

from cora.recipe.features.remove_method_required_role import tool
from cora.recipe.features.remove_method_required_role.command import (
    RemoveMethodRequiredRole,
)
from cora.recipe.features.remove_method_required_role.decider import decide
from cora.recipe.features.remove_method_required_role.handler import Handler, bind
from cora.recipe.features.remove_method_required_role.route import router

__all__ = [
    "Handler",
    "RemoveMethodRequiredRole",
    "bind",
    "decide",
    "router",
    "tool",
]
