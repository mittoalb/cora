"""Pure decider for the `DecommissionMount` command.

## Invariants:

  - State must not be None -> MountNotFoundError.
  - Status must be Active -> MountCannotDecommissionError
    (re-decommission rejected).
  - Mount.installed_asset_id must be None (slot must be vacant)
    -> MountHasInstalledAssetError (operator must uninstall first;
    no implicit eviction per the design anti-hook).
  - context.active_child_mount_ids must be empty
    -> MountHasActiveChildrenError (no cascade-decommission per the
    design anti-hook; operator must decommission children first).
"""

from datetime import datetime

from cora.equipment.aggregates.mount import (
    Mount,
    MountCannotDecommissionError,
    MountDecommissioned,
    MountHasActiveChildrenError,
    MountHasInstalledAssetError,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.features.decommission_mount.command import DecommissionMount
from cora.equipment.features.decommission_mount.context import DecommissionMountContext


def decide(
    state: Mount | None,
    command: DecommissionMount,
    *,
    context: DecommissionMountContext,
    now: datetime,
) -> list[MountDecommissioned]:
    """Decide the events produced by decommissioning an existing mount."""
    if state is None:
        raise MountNotFoundError(command.mount_id)
    if state.status is not MountStatus.ACTIVE:
        msg = (
            f"currently in status {state.status.value}, "
            f"decommission requires {MountStatus.ACTIVE.value}"
        )
        raise MountCannotDecommissionError(state.id, msg)
    if state.installed_asset_id is not None:
        raise MountHasInstalledAssetError(state.id, state.installed_asset_id)
    if context.active_child_mount_ids:
        raise MountHasActiveChildrenError(state.id, context.active_child_mount_ids)
    return [
        MountDecommissioned(
            mount_id=state.id,
            reason=command.reason,
            occurred_at=now,
        )
    ]
