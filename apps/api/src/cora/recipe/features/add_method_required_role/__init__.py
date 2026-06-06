"""Vertical slice for the `AddMethodRequiredRole` command.

Adds a single `RoleRequirement` (positional role slot; IEC 81346
Function aspect) to an existing Method's required_roles set;
strict-not-idempotent on role_name: a duplicate role_name
surfaces as 409 rather than silent no-op. The lifecycle guard
mirrors `update_method_parameters_schema` in spirit but is stricter:
required-roles mutations are restricted to the `Defined` status.

Module-as-namespace surface:

    from cora.recipe.features import add_method_required_role

    cmd = add_method_required_role.AddMethodRequiredRole(
        method_id=...,
        requirement=RoleRequirement(
            role_name=RoleName("detector"),
            family_id=...,
            required_ports=frozenset(...),
            optional=False,
        ),
    )
    handler = add_method_required_role.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

See [[project-method-required-roles-design]] for the full design
lock and [[project-equipment-isa-gap-research]] for the Function-
aspect gap context. The Plan-side role bindings and the
Wire-role-endpoint invariant live in `bind_plan_role` /
`unbind_plan_role` / `add_plan_wire`.
"""

from cora.recipe.features.add_method_required_role import tool
from cora.recipe.features.add_method_required_role.command import AddMethodRequiredRole
from cora.recipe.features.add_method_required_role.decider import decide
from cora.recipe.features.add_method_required_role.handler import Handler, bind
from cora.recipe.features.add_method_required_role.route import router

__all__ = [
    "AddMethodRequiredRole",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
