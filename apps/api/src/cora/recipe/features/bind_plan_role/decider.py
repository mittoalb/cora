"""Pure decider for the `BindPlanRole` command.

Mirrors the cross-aggregate-read pattern from `add_plan_wire`. The
context object is constructed by the handler from `load_method` +
`load_asset`; tests pass it directly to bypass the I/O. Fail-fast
order is the same as the Invariants list below.

Invariants:
  - State must not be None -> PlanNotFoundError
  - Plan must be in Defined status -> PlanCannotMutateRoleBindingsError
  - command.asset_id must be in state.asset_ids ->
    PlanRoleAssetNotBoundError
  - role_name must not already be in state.role_bindings (strict-not-
    idempotent) -> PlanRoleAlreadyBoundError
  - Method must be loaded via state.method_id -> MethodNotFoundError
  - role_name must match a RoleRequirement on method.required_roles
    -> PlanRoleNameNotDeclaredError
  - Asset must be loaded -> AssetNotFoundError
  - Bound Asset's family_ids must include the role's family_id ->
    PlanRoleFamilyMismatchError
  - Bound Asset's ports must cover every entry in the role's
    required_ports (exact triple match on port_name, direction,
    signal_type) -> PlanRolePortCoverageNotSatisfiedError
"""

from datetime import datetime

from cora.equipment.aggregates.asset import AssetNotFoundError
from cora.recipe.aggregates.method import MethodNotFoundError, RoleRequirement
from cora.recipe.aggregates.plan import (
    Plan,
    PlanCannotMutateRoleBindingsError,
    PlanNotFoundError,
    PlanRoleAlreadyBoundError,
    PlanRoleAssetNotBoundError,
    PlanRoleBound,
    PlanRoleFamilyMismatchError,
    PlanRoleNameNotDeclaredError,
    PlanRolePortCoverageNotSatisfiedError,
    PlanStatus,
)
from cora.recipe.features.bind_plan_role.command import BindPlanRole
from cora.recipe.features.bind_plan_role.context import BindPlanRoleContext


def decide(
    state: Plan | None,
    command: BindPlanRole,
    *,
    context: BindPlanRoleContext,
    now: datetime,
) -> list[PlanRoleBound]:
    """Decide the events produced by binding a role to an Asset."""
    if state is None:
        raise PlanNotFoundError(command.plan_id)

    if state.status is not PlanStatus.DEFINED:
        raise PlanCannotMutateRoleBindingsError(state.id, state.status)

    if command.asset_id not in state.asset_ids:
        raise PlanRoleAssetNotBoundError(state.id, command.role_name, command.asset_id)

    if any(b.role_name == command.role_name for b in state.role_bindings):
        raise PlanRoleAlreadyBoundError(state.id, command.role_name)

    method = context.method
    if method is None:
        # state.method_id is None on legacy Plans or the cross-load
        # missed; surfacing MethodNotFoundError matches add_plan_wire's
        # AssetNotFoundError convention for missing cross-BC streams.
        # method_id is the Plan's bound Method; bare uuid4() sentinel
        # not appropriate because state.method_id may be None.
        raise MethodNotFoundError(state.method_id or command.plan_id)

    matching_role: RoleRequirement | None = None
    for role in method.required_roles:
        if role.role_name == command.role_name:
            matching_role = role
            break
    if matching_role is None:
        raise PlanRoleNameNotDeclaredError(state.id, method.id, command.role_name)

    asset = context.asset
    if asset is None:
        raise AssetNotFoundError(command.asset_id)

    if matching_role.family_id not in asset.family_ids:
        raise PlanRoleFamilyMismatchError(
            state.id,
            command.role_name,
            command.asset_id,
            matching_role.family_id,
            asset.family_ids,
        )

    # Port coverage: each required (port_name, direction, signal_type)
    # triple must match an existing Asset.port triple exactly.
    asset_port_triples = {(p.name, p.direction, p.signal_type) for p in asset.ports}
    missing: list[tuple[str, str, str]] = []
    for required in matching_role.required_ports:
        triple = (required.port_name, required.direction, required.signal_type)
        if triple not in asset_port_triples:
            missing.append((triple[0], triple[1].value, triple[2]))
    if missing:
        raise PlanRolePortCoverageNotSatisfiedError(
            state.id,
            command.role_name,
            command.asset_id,
            missing,
        )

    return [
        PlanRoleBound(
            plan_id=state.id,
            role_name=command.role_name.value,
            asset_id=command.asset_id,
            occurred_at=now,
        )
    ]
