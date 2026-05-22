"""The `RemovePlanWire` command — intent dataclass for this slice.

`plan_id` is the target Plan aggregate. The four port-reference
fields together identify the Wire to remove (the 4-tuple IS the
Wire's identity).

Validation (in the decider, not here):
  - the Wire must exist in `state.wires` (strict-not-idempotent;
    raises `PlanWireNotFoundError` if absent — symmetric with
    `add_plan_wire`'s strict-not-idempotent re-add behavior)

NOTE: the decider does NOT re-validate direction / signal_type /
asset-binding / port-existence on remove. The Wire was validated
at add-time, and removal is a structural operation on the wire
SET that doesn't need cross-aggregate context. Hot-swap procedure
per [[project_plan_wiring_design]] expects operators to remove
wires BEFORE the referenced ports / Assets are removed.

Mirrors `RemoveAssetPort` shape from 5h.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RemovePlanWire:
    """Remove a typed port-to-port Wire from an existing Plan's wire set."""

    plan_id: UUID
    source_asset_id: UUID
    source_port_name: str
    target_asset_id: UUID
    target_port_name: str
