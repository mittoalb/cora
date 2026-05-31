"""Context snapshot loaded by the install_asset handler.

The install_asset slice uses single-stream-write + projection-
precondition. The handler loads two projection facets BEFORE calling
the pure decider:

  - `asset_lifecycle`: from proj_equipment_asset_summary. None means
    no Asset row exists -> AssetNotFoundForMountError. Non-Active
    means the Asset is pre-service / pulled / retired ->
    AssetNotInstallableError.
  - `currently_installed_at_mount_id`: from proj_equipment_asset_location.
    Non-None and != command.mount_id means the Asset is already in
    another Mount; single-source-of-truth invariant requires the
    operator to uninstall from the current Mount first ->
    AssetAlreadyInstalledElsewhereError.

Mount-side checks (status, occupancy, same-asset idempotency) live
on the Mount aggregate state and are tested by the decider directly
without needing context.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class InstallAssetContext:
    """Two projection facets the decider needs: Asset lifecycle + back-lookup."""

    asset_lifecycle: str | None
    currently_installed_at_mount_id: UUID | None
