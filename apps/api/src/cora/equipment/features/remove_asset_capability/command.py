"""The `RemoveAssetCapability` command — intent dataclass for this slice.

Mirror of `AddAssetCapability`. Operators remove a Capability when
retiring a technique from an asset (instrument upgrade, vendor
removal, capability moved to a different asset, etc.).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RemoveAssetCapability:
    """Remove a Capability from an existing asset's capability set."""

    asset_id: UUID
    capability_id: UUID
