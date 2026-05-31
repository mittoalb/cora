"""The `RegisterFrame` command - intent dataclass for the register_frame slice.

Carries the caller-controlled fields: the frame's display name,
its optional parent frame, its optional Placement relative to the
parent, and its optional supersedes link. Server-side concerns (new
frame id, wall-clock timestamp, correlation id, per-event ids) are
injected by the handler from infrastructure ports, matching the
cross-BC create-style command shape locked in Access / Trust /
Subject / Equipment.

`parent_frame_id` is `UUID | None` and `placement`
is `Placement | None`. The "both together or both None" invariant
(root frames have both None; child frames have both non-None and
`placement.parent_frame_id == parent_frame_id`) is enforced by the
decider via `InvalidFrameRootError`.

`supersedes` is `FrameRevisionLink | None`. When present, marks
this frame as a revision of an older frame; the decider rejects
self-supersession (predecessor_frame_id == frame_id) via
`FrameCannotSupersedeError`. Predecessor existence is NOT verified
at write time (eventual-consistency stance, matching Mount.placement
.parent_frame_id precedent). Immutable post-register (no
`update_supersedes` slice in v1).

Eventual-consistency stance for `parent_frame_id` and
`supersedes.predecessor_frame_id`: the decider does NOT verify the
referenced parent / predecessor Frame exists in the event store at
write time; the handler's optional projection-precondition check
(cycle defense, parent active-status check) covers the most common
data-integrity failures without requiring full stream walks.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates._placement import Placement
from cora.equipment.aggregates.frame.state import FrameRevisionLink


@dataclass(frozen=True)
class RegisterFrame:
    """Register a new frame with the given name, parent, placement, and supersedes link."""

    name: str
    parent_frame_id: UUID | None
    placement: Placement | None
    supersedes: FrameRevisionLink | None = None
