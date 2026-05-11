"""Pure decider for the `RestoreFromMaintenance` command.

Single-source-state transition: `Maintenance -> Active`. The
inverse of `enter_maintenance`.

Invariants:
  - State must not be None (asset must exist) -> AssetNotFoundError
  - State must be in `Maintenance` (the only state from which
    restore-from-maintenance is valid)
    -> AssetCannotRestoreFromMaintenanceError(current_lifecycle=...)

Strict semantics, not idempotent: restoring an already-`Active`
asset raises rather than no-op (the maintenance window has already
ended). Same precedent as `activate_asset` / `enter_maintenance`.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotRestoreFromMaintenanceError,
    AssetLifecycle,
    AssetNotFoundError,
    AssetRestoredFromMaintenance,
)
from cora.equipment.features.restore_from_maintenance.command import RestoreFromMaintenance


def decide(
    state: Asset | None,
    command: RestoreFromMaintenance,
    *,
    now: datetime,
) -> list[AssetRestoredFromMaintenance]:
    """Decide the events produced by restoring an asset from maintenance."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)
    if state.lifecycle is not AssetLifecycle.MAINTENANCE:
        raise AssetCannotRestoreFromMaintenanceError(state.id, current_lifecycle=state.lifecycle)
    return [AssetRestoredFromMaintenance(asset_id=state.id, occurred_at=now)]
