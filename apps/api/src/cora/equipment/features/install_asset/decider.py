"""Pure decider for the `InstallAsset` command.

## Invariants:

  - State must not be None -> MountNotFoundError.
  - Status must be Active -> MountCannotUpdateError (decommissioned
    mounts cannot accept new specimens).
  - If the slot already holds the same Asset the caller is trying to
    install, the call is an idempotent no-op (return []). This
    matches PUT's RFC 9110 idempotency contract; without it a
    flaky-network retry surfaces 409 on the second attempt.
  - context.asset_lifecycle must be non-None -> AssetNotFoundForMountError
    (the Asset has no event-store stream / projection row).
  - context.asset_lifecycle must be 'Active' -> AssetNotInstallableError
    (Commissioned Assets are pre-service; Maintenance are pulled;
    Decommissioned are retired; none belong in a live equipment slot).
  - context.currently_installed_at_mount_id must be None OR equal to
    state.id -> AssetAlreadyInstalledElsewhereError. Enforces the
    single-source-of-truth invariant: an Asset can occupy AT MOST
    ONE Mount slot at a time. (state.id is the Mount we're installing
    into; if the Asset is already in THIS Mount we'd have returned
    [] above as a no-op idempotent path.)
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
    AssetAlreadyInstalledElsewhereError,
    AssetNotFoundForMountError,
    AssetNotInstallableError,
    Mount,
    MountAlreadyOccupiedError,
    MountAssetInstalled,
    MountCannotUpdateError,
    MountNotFoundError,
    MountStatus,
)
from cora.equipment.features.install_asset.command import InstallAsset
from cora.equipment.features.install_asset.context import InstallAssetContext

_ACTIVE_LIFECYCLE = "Active"


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
    if state.installed_asset_id == command.asset_id:
        # Same Asset already installed in this Mount: idempotent no-op
        # per PUT's RFC 9110 contract. Skip downstream projection checks
        # since the requested state is already true.
        return []
    if context.asset_lifecycle is None:
        raise AssetNotFoundForMountError(command.asset_id)
    if context.asset_lifecycle != _ACTIVE_LIFECYCLE:
        raise AssetNotInstallableError(command.asset_id, context.asset_lifecycle)
    if (
        context.currently_installed_at_mount_id is not None
        and context.currently_installed_at_mount_id != state.id
    ):
        raise AssetAlreadyInstalledElsewhereError(
            command.asset_id,
            context.currently_installed_at_mount_id,
            state.id,
        )
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
