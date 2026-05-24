"""Pure decider for the `RemovePlanWire` command.

Mirror of `add_plan_wire.decide` minus the cross-aggregate validation:

  1. Plan stream must have prior events → `PlanNotFoundError` if state is None
  2. Construct the proposed `Wire` (raises `InvalidWireError` on bad
     port name lengths)
  3. Strict-not-idempotent: if the wire is NOT in `state.wires`,
     raise `PlanWireNotFoundError` (symmetric with add's behavior).

No cross-aggregate context needed: removal is a pure set-difference
operation. Asset / port state can have changed since the wire was
added (operators may have removed ports between add and remove —
that's fine, the wire still has identity in the wire set and can
be removed). See [[project_plan_wiring_design]] §hot-swap procedure.
"""

from datetime import datetime

from cora.recipe.aggregates.plan import (
    Plan,
    PlanNotFoundError,
    PlanWireNotFoundError,
    PlanWireRemoved,
    Wire,
)
from cora.recipe.features.remove_plan_wire.command import RemovePlanWire


def decide(
    state: Plan | None,
    command: RemovePlanWire,
    *,
    now: datetime,
) -> list[PlanWireRemoved]:
    """Decide the events produced by removing a Wire from an existing Plan.

    Invariants:
      - State must not be None -> PlanNotFoundError
      - Wire structural shape must be valid -> InvalidWireError
        (via Wire VO)
      - Wire must be in state.wires (strict-not-idempotent)
        -> PlanWireNotFoundError
    """
    if state is None:
        raise PlanNotFoundError(command.plan_id)

    proposed = Wire(
        source_asset_id=command.source_asset_id,
        source_port_name=command.source_port_name,
        target_asset_id=command.target_asset_id,
        target_port_name=command.target_port_name,
    )

    if proposed not in state.wires:
        raise PlanWireNotFoundError(proposed)

    return [
        PlanWireRemoved(
            plan_id=state.id,
            source_asset_id=proposed.source_asset_id,
            source_port_name=proposed.source_port_name,
            target_asset_id=proposed.target_asset_id,
            target_port_name=proposed.target_port_name,
            occurred_at=now,
        )
    ]
