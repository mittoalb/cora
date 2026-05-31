"""The `UpdateMountPlacement` command - intent dataclass for the update_mount_placement slice."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cora.equipment.aggregates._placement import Placement


@dataclass(frozen=True)
class UpdateMountPlacement:
    """Update a mount's placement (re-survey or initial-from-drawing)."""

    mount_id: UUID
    new_placement: Placement
    survey: dict[str, Any] | None
