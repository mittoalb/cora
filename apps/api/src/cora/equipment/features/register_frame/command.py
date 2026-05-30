"""The `RegisterFrame` command - intent dataclass for the register_frame slice.

Carries the caller-controlled fields: the frame's display name,
its optional parent frame, and its optional Placement relative to
the parent. Server-side concerns (new frame id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports, matching the cross-BC create-style command
shape locked in Access / Trust / Subject / Equipment.

`parent_frame_id` is `UUID | None` and `placement_relative_to_parent`
is `Placement | None`. The "both together or both None" invariant
(root frames have both None; child frames have both non-None and
`placement.parent_frame == parent_frame_id`) is enforced by the
decider via `InvalidFrameRootError`.

Eventual-consistency stance for `parent_frame_id`: the decider does
NOT verify the referenced parent Frame exists in the event store at
write time; the handler's optional projection-precondition check
(cycle defense, parent active-status check) covers the most common
data-integrity failures without requiring full stream walks.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates._placement import Placement


@dataclass(frozen=True)
class RegisterFrame:
    """Register a new frame with the given name, parent, and placement."""

    name: str
    parent_frame_id: UUID | None
    placement_relative_to_parent: Placement | None
