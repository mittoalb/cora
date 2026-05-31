"""Pure decider for the `ExitMaintenance` command.

Single-source-state transition: `Maintenance -> Active`. The
inverse of `enter_maintenance`.

Invariants:
  - State must not be None (asset must exist) -> AssetNotFoundError
  - State must be in `Maintenance` (the only state from which
    exit-maintenance is valid)
    -> AssetCannotExitMaintenanceError(current_lifecycle=...)

Strict semantics, not idempotent: exiting maintenance on an
already-`Active` asset raises rather than no-op (the maintenance
window has already ended). Same precedent as `activate_asset` /
`enter_maintenance`.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotExitMaintenanceError,
    AssetLifecycle,
    AssetMaintenanceExited,
    AssetNotFoundError,
)
from cora.equipment.features.exit_maintenance.command import ExitMaintenance


def decide(
    state: Asset | None,
    command: ExitMaintenance,
    *,
    now: datetime,
) -> list[AssetMaintenanceExited]:
    """Decide the events produced by exiting maintenance on an asset."""
    if state is None:
        raise AssetNotFoundError(command.asset_id)
    if state.lifecycle is not AssetLifecycle.MAINTENANCE:
        raise AssetCannotExitMaintenanceError(state.id, current_lifecycle=state.lifecycle)
    return [AssetMaintenanceExited(asset_id=state.id, occurred_at=now)]
