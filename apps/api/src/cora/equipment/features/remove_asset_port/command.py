"""The `RemoveAssetPort` command — intent dataclass for this slice (Phase 5h)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RemoveAssetPort:
    """Remove a typed port from an existing Asset's port set.

    The port is identified by `port_name` (unique within the
    Asset's scope). The decider rejects when the asset is
    Decommissioned or no port with this name exists.
    """

    asset_id: UUID
    port_name: str
