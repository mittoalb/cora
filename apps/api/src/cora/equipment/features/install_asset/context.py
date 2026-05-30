"""Context snapshot loaded by the install_asset handler.

The install_asset slice uses single-stream-write + projection-
precondition. The handler loads the asset_lookup projection (does
the Asset exist?) BEFORE calling the pure decider; the decider
raises AssetNotFoundForMountError if the Asset is missing.

Mount-side checks (status, occupancy) live on the Mount aggregate
state and are tested by the decider directly without needing context.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class InstallAssetContext:
    """Snapshot of Asset existence from the asset_lookup projection."""

    asset_exists: bool
