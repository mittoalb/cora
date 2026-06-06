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
  - No existing wire's endpoint may claim the role's required_port
    (matched by port_name + direction side) at an Asset other than
    the candidate bound Asset. Without this scan the wire-then-bind
    and unbind-rebind orderings silently divergence the role table
    from the wire graph -> PlanWireRoleEndpointMismatchError
"""

from datetime import datetime

from cora.equipment.aggregates.asset import AssetNotFoundError, PortDirection
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
    PlanWireRoleEndpointMismatchError,
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
        # Unlike `add_plan_wire`, this decider CANNOT proceed without a
        # Method: the role_name must be validated against
        # method.required_roles, and there is no fallback semantic that
        # could justify silently binding to an unknown role. The
        # asymmetry with add_plan_wire (which silently skips the role
        # check when method is None) is principled and documented in
        # the add_plan_wire decider. `state.method_id or command.plan_id`
        # surfaces the better sentinel: prefer the genuine method_id when
        # the Plan declares one, otherwise echo plan_id so the operator
        # sees the offending Plan.
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

    # Wire-graph consistency: scan existing wires for any endpoint
    # that already claims this role's port (by name + side) at a
    # different Asset than the candidate binding. Without this scan,
    # the wire-then-bind temporal ordering (operator adds a wire
    # before binding the role) and the unbind-rebind ordering
    # (operator unbinds a role while wires still reference its
    # port, then rebinds to a different Asset) would silently
    # produce role-table-vs-wire-graph divergence. The add_plan_wire
    # decider already enforces the bind-then-wire ordering; this
    # branch closes the bind ordering symmetrically. Mirrors the
    # add_plan_wire role-endpoint check exactly: OUTPUT required_ports
    # constrain wire SOURCE endpoints, INPUT required_ports constrain
    # wire TARGET endpoints.
    for required in matching_role.required_ports:
        if required.direction is PortDirection.OUTPUT:
            for wire in state.wires:
                if (
                    wire.source_port_name == required.port_name
                    and wire.source_asset_id != command.asset_id
                ):
                    raise PlanWireRoleEndpointMismatchError(
                        state.id,
                        wire,
                        command.role_name,
                        "source",
                        command.asset_id,
                        wire.source_asset_id,
                    )
        if required.direction is PortDirection.INPUT:
            for wire in state.wires:
                if (
                    wire.target_port_name == required.port_name
                    and wire.target_asset_id != command.asset_id
                ):
                    raise PlanWireRoleEndpointMismatchError(
                        state.id,
                        wire,
                        command.role_name,
                        "target",
                        command.asset_id,
                        wire.target_asset_id,
                    )

    return [
        PlanRoleBound(
            plan_id=state.id,
            role_name=command.role_name.value,
            asset_id=command.asset_id,
            occurred_at=now,
        )
    ]
