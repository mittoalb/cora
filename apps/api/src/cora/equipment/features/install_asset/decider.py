"""Pure decider for the `InstallAsset` command.

## Invariants:

  - State must not be None -> MountNotFoundError.
  - Status must be Active -> MountCannotUpdateError (decommissioned
    mounts cannot accept new specimens).
  - context.asset_exists must be True -> AssetNotFoundForMountError
    (the Asset has no event-store stream / projection row). Checked
    before occupancy so the more diagnostic failure surfaces first
    when the operator's chosen asset_id is bogus on an occupied slot.
  - Mount.installed_asset_id must be None -> MountAlreadyOccupiedError
    (no implicit eviction per the design anti-hook; operator must
    uninstall_asset first).

`previously_installed_asset_id` is always None today: the no-implicit-
eviction anti-hook means the slot is vacant by precondition, so there
is no prior specimen to record. The MountAssetInstalled event field
is reserved for a future swap_asset slice that does uninstall+install
atomically (Watch in the design memo).
"""

from datetime import datetime

from cora.equipment.aggregates.mount import (
    Mount,
    MountAlreadyOccupiedError,
    MountAssetInstalled,
    MountCannotUpdateError,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.aggregates.mount.state import AssetNotFoundForMountError
from cora.equipment.features.install_asset.command import InstallAsset
from cora.equipment.features.install_asset.context import InstallAssetContext


def decide(
    state: Mount | None,
    command: InstallAsset,
    *,
    context: InstallAssetContext,
    now: datetime,
) -> list[MountAssetInstalled]:
    """Decide the events produced by installing an Asset into a Mount."""
    if state is None:
        raise MountNotFoundError(command.mount_id)
    if state.status is not MountStatus.ACTIVE:
        msg = (
            f"currently in status {state.status.value}, "
            f"install_asset requires {MountStatus.ACTIVE.value}"
        )
        raise MountCannotUpdateError(state.id, msg)
    if not context.asset_exists:
        raise AssetNotFoundForMountError(command.asset_id)
    if state.installed_asset_id is not None:
        raise MountAlreadyOccupiedError(
            state.id,
            state.installed_asset_id,
            command.asset_id,
        )
    return [
        MountAssetInstalled(
            mount_id=state.id,
            asset_id=command.asset_id,
            previously_installed_asset_id=None,
            occurred_at=now,
        )
    ]
