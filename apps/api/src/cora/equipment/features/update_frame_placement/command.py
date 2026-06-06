"""The `UpdateFramePlacement` command - intent dataclass for the update_frame_placement slice.

Update-style: targets an existing Frame by `frame_id`. Carries the
new Placement (whose `parent_frame_id` must equal the Frame's
existing `parent_id`, enforced by the decider) and an optional
`survey` payload for re-survey provenance.

The decider's no-op-on-unchanged contract (via
`make_frame_update_handler` / `make_update_handler` factory) means
an UpdateFramePlacement with `new_placement == current_placement` emits zero
events and is harmless to retry.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cora.equipment.aggregates._placement import Placement


@dataclass(frozen=True)
class UpdateFramePlacement:
    """Update a frame's placement."""

    frame_id: UUID
    new_placement: Placement
    survey: dict[str, Any] | None
