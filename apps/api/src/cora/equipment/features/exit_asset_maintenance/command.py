"""The `ExitAssetMaintenance` command, intent dataclass for this slice.

`asset_id` is the **target** Asset aggregate (the asset being
returned to active service after a maintenance window). The
principal-id of the invoker is supplied separately by the
application handler at call time. Mirrors `EnterAssetMaintenance` shape
exactly (single-source transition).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ExitAssetMaintenance:
    """Return an existing (Maintenance) asset to active service."""

    asset_id: UUID
