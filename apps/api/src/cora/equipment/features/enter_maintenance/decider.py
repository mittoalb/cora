"""Pure decider for the `EnterMaintenance` command.

Single-source-state transition: `Active -> Maintenance`. Industrial
convention: only in-service assets enter maintenance (Commissioned
ones are still pre-service; Decommissioned ones are retired).

Invariants:
  - State must not be None (asset must exist) -> AssetNotFoundError
  - State must be in `Active` (the only state from which entering
    maintenance is valid) -> AssetCannotEnterMaintenanceError(current_lifecycle=...)

Strict semantics, not idempotent: re-entering maintenance on an
already-`Maintenance` asset raises rather than no-op or always-emit.
Same precedent as `activate_asset` / `mount_subject`.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotEnterMaintenanceError,
    AssetLifecycle,
    AssetMaintenanceEntered,
    AssetNotFoundError,
)
from cora.equipment.features.enter_maintenance.command import EnterMaintenance


def decide(
    state: Asset | None,
    command: EnterMaintenance,
    *,
    now: datetime,
) -> list[AssetMaintenanceEntered]:
    """Decide the events produced by entering maintenance on an existing asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)
    if state.lifecycle is not AssetLifecycle.ACTIVE:
        raise AssetCannotEnterMaintenanceError(state.id, current_lifecycle=state.lifecycle)
    return [AssetMaintenanceEntered(asset_id=state.id, occurred_at=now)]
