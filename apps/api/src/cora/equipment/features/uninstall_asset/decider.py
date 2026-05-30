"""Pure decider for the `UninstallAsset` command.

## Invariants:

  - State must not be None -> MountNotFoundError.
  - Status must be Active -> MountCannotUpdateError (decommissioned
    mounts cannot mutate occupancy).
  - Mount.installed_asset_id must be non-None -> MountIsEmptyError
    (cannot uninstall from a vacant slot).
"""

from datetime import datetime

from cora.equipment.aggregates.mount import (
    Mount,
    MountAssetUninstalled,
    MountCannotUpdateError,
    MountIsEmptyError,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.features.uninstall_asset.command import UninstallAsset


def decide(
    state: Mount | None,
    command: UninstallAsset,
    *,
    now: datetime,
) -> list[MountAssetUninstalled]:
    """Decide the events produced by uninstalling a Mount's occupant."""
    if state is None:
        raise MountNotFoundError(command.mount_id)
    if state.status is not MountStatus.ACTIVE:
        msg = (
            f"currently in status {state.status.value}, "
            f"uninstall_asset requires {MountStatus.ACTIVE.value}"
        )
        raise MountCannotUpdateError(state.id, msg)
    if state.installed_asset_id is None:
        raise MountIsEmptyError(state.id)
    return [
        MountAssetUninstalled(
            mount_id=state.id,
            asset_id=state.installed_asset_id,
            reason=command.reason,
            occurred_at=now,
        )
    ]
