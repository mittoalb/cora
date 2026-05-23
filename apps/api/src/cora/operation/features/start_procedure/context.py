"""Cross-aggregate context the `start_procedure` decider validates against.

`ProcedureStartContext` is built by the `start_procedure` handler
from `load_asset` calls (one per target Asset id) before reaching the
pure decider. The decider treats the loaded entities as opaque domain
data and validates the start preconditions without performing any
I/O.

This is the third decider in the codebase that takes upstream
aggregate state as input (after Plan's `define_plan` and Run's
`start_run`). Per the canonical pattern documented in
CONTRIBUTING.md: handler pre-loads, decider receives an immutable
context dataclass, no I/O in the decider.

Slice-local module by design: only `start_procedure` uses it today.

## Field semantics

  - `assets`: dict keyed by asset_id, loaded from
    `procedure.target_asset_ids`. Decider rejects if any is
    Decommissioned (`ProcedureAssetDecommissionedError`). Empty dict
    is valid (facility-envelope procedures, for example beam-mode
    change, have no target Assets).

## Future-additive fields (deferred per project_operation_design)

  - `supply_availability` -- Supply BC integration. The needs-Supplies
    side ships at Method (10b) but Supply gating at start time is
    deferred until a real consumer surfaces.
  - `decision_approval` -- Decision BC integration. Same deferral.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.asset import Asset


@dataclass(frozen=True)
class ProcedureStartContext:
    """Snapshot of upstream aggregate state at Procedure-start time.

    `assets` is loaded from `procedure.target_asset_ids` (empty dict
    when target_asset_ids is the empty frozenset, valid for facility-
    envelope procedures).
    """

    assets: dict[UUID, Asset]
