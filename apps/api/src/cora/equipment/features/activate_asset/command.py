"""The `ActivateAsset` command — intent dataclass for this slice.

`asset_id` is the **target** Asset aggregate (the asset being
activated). The principal-id of the invoker is supplied separately
by the application handler at call time. Mirrors `MountSubject` /
`MeasureSubject`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ActivateAsset:
    """Activate an existing (Commissioned) asset, putting it into service."""

    asset_id: UUID
