"""The `EnterAssetMaintenance` command — intent dataclass for this slice.

`asset_id` is the **target** Asset aggregate (the asset being taken
into a maintenance window). The principal-id of the invoker is
supplied separately by the application handler at call time.
Mirrors `ActivateAsset` shape exactly (single-source transition).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class EnterAssetMaintenance:
    """Take an existing (Active) asset out of service for maintenance."""

    asset_id: UUID
