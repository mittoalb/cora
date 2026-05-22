"""The `AddPlanWire` command — intent dataclass for this slice.

`plan_id` is the target Plan aggregate. The four port-reference
fields together identify the Wire to add (no separate `wire_id` —
the 4-tuple IS the identity, see [[project_plan_wiring_design]]).

Validation (in the decider, not here):
  - source port must have `direction=OUTPUT`
  - target port must have `direction=INPUT`
  - source/target ports must have matching `signal_type`
  - both endpoint asset_ids must be in the Plan's `asset_ids` set
  - both endpoint port_names must exist on their respective Asset.ports
  - target port can be the destination of at most one Wire (fan-in
    forbidden; escape hatch is a `Combiner` Family Asset)
  - self-loops on the SAME port are rejected; self-loops between
    DIFFERENT ports on the same Asset are allowed
  - re-adding an already-present Wire raises `PlanWireAlreadyExistsError`
    (strict-not-idempotent, mirrors 5h `add_asset_port`)

Mirrors `AddAssetPort` shape from 5h.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AddPlanWire:
    """Add a typed port-to-port Wire to an existing Plan's wire set."""

    plan_id: UUID
    source_asset_id: UUID
    source_port_name: str
    target_asset_id: UUID
    target_port_name: str
