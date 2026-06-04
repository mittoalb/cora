"""Context snapshot loaded by the decommission_asset handler.

Mirrors install_asset's context shape on the inverse side. The
handler loads which Mount currently holds this Asset from the
`proj_equipment_asset_location` projection BEFORE calling the pure
decider; the decider raises `AssetIsInstalledError` when the
back-lookup returns a non-None mount_id.

The `AssetHasFixtureBinding` precondition is a STATE-based check on
`Asset.fixture_id` (no projection lookup); the decider raises
directly from state. Same pattern as `decommission_mount`'s
`MountHasInstalledAsset` (state-based) vs `MountHasActiveChildren`
(projection-based).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DecommissionAssetContext:
    """One projection facet: the Mount currently holding this Asset, or None."""

    currently_installed_at_mount_id: UUID | None
