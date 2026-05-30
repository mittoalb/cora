"""Context snapshot loaded by the decommission_mount handler.

Mirrors decommission_frame's context shape. The handler loads
active children from mount_children projection BEFORE calling the
pure decider; the decider raises MountHasActiveChildrenError if the
tuple is non-empty.

The MountHasInstalledAsset precondition (slot must be vacant) is a
STATE-based check on Mount.installed_asset_id, not a projection
lookup; it lives in the decider directly.
"""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class DecommissionMountContext:
    """Snapshot of active child mounts from mount_children projection."""

    active_child_mount_ids: tuple[UUID, ...] = field(default_factory=tuple)
