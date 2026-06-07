"""Pure decider for the `AddPlanWire` command.

Validation cascade (fail-fast, in order):

  1. Plan stream must have prior events -> `PlanNotFoundError` if state is None
  2. Construct the proposed `Wire` (raises `InvalidWireError` on bad
     port name lengths)
  3. Strict-not-idempotent: if the proposed wire is already in
     `state.wires`, raise `PlanWireAlreadyExistsError`. Mirrors 5h
     `add_asset_port`.
  4. Fan-in check: if any existing wire in `state.wires` already
     targets the same `(target_asset_id, target_port_name)` pair,
     raise `PlanWireTargetAlreadyConnectedError`. Done here (not in
     the structural validator) because it requires the current wire
     SET, which the handler doesn't have to load separately.
  5. Structural validation via `validate_wire_endpoints`:
     self-loop guard, asset-binding check, port-existence check,
     direction check, signal_type compatibility.
  6. PseudoAxis fan-out validation (only when the target Asset carries
     a non-None `partition_rule`): output cardinality, partition-rule
     arity, signal-type homogeneity across the FULL set of incoming
     wires (existing wires targeting the same Asset + the proposed
     wire). See `validate_pseudoaxis_fanout` for the contract.

Lifecycle independence: wiring is allowed in any Plan lifecycle
state (Defined, Versioned, Deprecated), same precedent as
`update_plan_default_parameters` (6g-b). Operators can adjust
wiring on a Versioned Plan without re-versioning. Deprecated Plans
also accept wire mutations (advisory deprecation; the lifecycle
gate is at Run-start, not Plan-mutation).

PseudoAxis-membership detection is self-gated on `partition_rule is
not None` (the same trigger `validate_pseudoaxis_fanout` already
applied at its (a) rule-presence guard). The earlier indirection
through a separate `pseudoaxis_family_ids` set + Family-name-match
in the handler is collapsed: the rule's presence on Asset state is
the single source of truth for "this Asset behaves as a virtual
axis".

See [[project_plan_wiring_design]].
"""

from datetime import datetime

from cora.equipment.aggregates.asset import PortDirection
from cora.recipe.aggregates.plan import (
    Plan,
    PlanNotFoundError,
    PlanWireAdded,
    PlanWireAlreadyExistsError,
    PlanWireRoleEndpointMismatchError,
    PlanWireTargetAlreadyConnectedError,
    Wire,
    validate_pseudoaxis_fanout,
    validate_wire_endpoints,
)
from cora.recipe.features.add_plan_wire.command import AddPlanWire
from cora.recipe.features.add_plan_wire.context import PlanWireContext


def decide(
    state: Plan | None,
    command: AddPlanWire,
    *,
    context: PlanWireContext,
    now: datetime,
) -> list[PlanWireAdded]:
    """Decide the events produced by adding a Wire to an existing Plan.

    Invariants:
      - State must not be None -> PlanNotFoundError
      - Wire structural shape must be valid -> InvalidWireError
        (via Wire VO)
      - Wire must not already be in state.wires
        (strict-not-idempotent) -> PlanWireAlreadyExistsError
      - (target_asset_id, target_port_name) must not already be
        connected (fan-in forbidden)
        -> PlanWireTargetAlreadyConnectedError
      - Endpoints must satisfy asset-binding, port existence,
        direction, and signal_type compatibility (no self-loop)
        -> InvalidWireError / wire-endpoint errors
        (via validate_wire_endpoints)
      - When the target Asset carries a non-None `partition_rule` the
        fan-out invariants hold for the SET of wires that will target
        the Asset after the add:
          - exactly one OUTPUT port declared on the Asset
            -> PlanPseudoAxisOutputCardinalityError
          - wire count matches the partition rule's declared arity
            (SolverReference exempt)
            -> PlanPseudoAxisArityMismatchError
          - all source-side signal_types match
            -> PlanPseudoAxisFanoutSignalTypeMismatchError
      - When `context.method` is loaded and Plan.role_bindings has an
        entry whose role's required_ports include the candidate
        wire's endpoint port_name on the matching direction, the
        wire's endpoint Asset MUST equal the role's bound Asset ->
        PlanWireRoleEndpointMismatchError (structural closure between
        Plan.role_bindings and Plan.wires)
    """
    if state is None:
        raise PlanNotFoundError(command.plan_id)

    # Construct the Wire VO (validates structural shape: port name
    # lengths, raises InvalidWireError to 400 at the route layer).
    proposed = Wire(
        source_asset_id=command.source_asset_id,
        source_port_name=command.source_port_name,
        target_asset_id=command.target_asset_id,
        target_port_name=command.target_port_name,
    )

    # Strict-not-idempotent: re-add raises (mirrors 5h add_asset_port).
    if proposed in state.wires:
        raise PlanWireAlreadyExistsError(proposed)

    # Fan-in check: at most one Wire per (target_asset_id, target_port_name).
    for existing in state.wires:
        if (
            existing.target_asset_id == proposed.target_asset_id
            and existing.target_port_name == proposed.target_port_name
        ):
            raise PlanWireTargetAlreadyConnectedError(proposed, existing)

    # Cross-aggregate structural validation (asset-binding + port-existence
    # + direction + signal_type + self-loop guard).
    validate_wire_endpoints(
        proposed,
        bound_asset_ids=state.asset_ids,
        assets_by_id=context.assets,
    )

    # PseudoAxis fan-out validation. The target Asset is in
    # context.assets after validate_wire_endpoints passes (the
    # port-existence branch keys against assets_by_id). Self-gated on
    # partition_rule presence: any Asset carrying a non-None rule is
    # the virtual-axis case the fan-out invariants are about.
    target_asset = context.assets[proposed.target_asset_id]
    if target_asset.partition_rule is not None:
        incoming_wires = frozenset(
            {w for w in state.wires if w.target_asset_id == proposed.target_asset_id} | {proposed}
        )
        validate_pseudoaxis_fanout(
            pseudoaxis_asset=target_asset,
            partition_rule=target_asset.partition_rule,
            incoming_wires=incoming_wires,
            assets_by_id=context.assets,
        )

    # Role-endpoint check: structural closure between Plan.role_bindings
    # and Plan.wires. For each RoleRequirement on the Plan's bound Method,
    # look at its required_ports. If the proposed wire's endpoint port
    # (source side for OUTPUT required_ports, target side for INPUT
    # required_ports) matches a required_port's name, the wire's
    # endpoint Asset MUST equal the Asset bound to that role on the
    # Plan. Skipped when the Method is not loaded (a Plan with no
    # method_id genuinely has no roles to validate against, so a wire
    # add can proceed) or when the role is not yet bound (operator
    # can wire before binding; the symmetric closure lives in
    # `bind_plan_role.decide`, which scans state.wires and rejects a
    # bind that would diverge from existing wire endpoints).
    #
    # The asymmetry with `bind_plan_role` (which raises
    # MethodNotFoundError when context.method is None) is principled:
    # bind cannot proceed without a method because role_name must be
    # validated against method.required_roles; wire CAN proceed because
    # the method is only consulted for the role-endpoint check, and
    # everything else (asset-binding, port-existence, fan-in, signal
    # type, pseudoaxis fan-out) stands on its own. Do not equalize.
    #
    # See [[project-plan-role-bindings-design]] for the rationale.
    if context.method is not None:
        binding_by_role_name = {b.role_name: b.asset_id for b in state.role_bindings}
        for role in context.method.required_roles:
            bound_asset_id = binding_by_role_name.get(role.role_name)
            if bound_asset_id is None:
                continue
            for required_port in role.required_ports:
                if (
                    required_port.direction is PortDirection.OUTPUT
                    and proposed.source_port_name == required_port.port_name
                    and proposed.source_asset_id != bound_asset_id
                ):
                    raise PlanWireRoleEndpointMismatchError(
                        state.id,
                        proposed,
                        role.role_name,
                        "source",
                        bound_asset_id,
                        proposed.source_asset_id,
                    )
                if (
                    required_port.direction is PortDirection.INPUT
                    and proposed.target_port_name == required_port.port_name
                    and proposed.target_asset_id != bound_asset_id
                ):
                    raise PlanWireRoleEndpointMismatchError(
                        state.id,
                        proposed,
                        role.role_name,
                        "target",
                        bound_asset_id,
                        proposed.target_asset_id,
                    )

    return [
        PlanWireAdded(
            plan_id=state.id,
            source_asset_id=proposed.source_asset_id,
            source_port_name=proposed.source_port_name,
            target_asset_id=proposed.target_asset_id,
            target_port_name=proposed.target_port_name,
            occurred_at=now,
        )
    ]
