"""The `UpdatePlacement` command - intent dataclass for the update_placement slice."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cora.equipment.aggregates._placement import Placement


@dataclass(frozen=True)
class UpdatePlacement:
    """Update a mount's placement (re-survey or initial-from-drawing)."""

    mount_id: UUID
    new_placement: Placement
    survey: dict[str, Any] | None
