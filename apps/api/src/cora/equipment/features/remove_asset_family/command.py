"""The `RemoveAssetFamily` command — intent dataclass for this slice.

Mirror of `AddAssetFamily`. Operators remove a Family when
retiring a technique from an asset (instrument upgrade, vendor
removal, family moved to a different asset, etc.).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RemoveAssetFamily:
    """Remove a Family from an existing asset's family set."""

    asset_id: UUID
    family_id: UUID
