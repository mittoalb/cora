"""Context snapshot loaded by the decommission_frame handler.

The decommission_frame slice uses single-stream-write + projection-
precondition (Visit BC precedent). The handler loads the
`frame_consumers` projection before calling the decider; the
context VO carries the active consumer ids so the pure decider can
reject the command without I/O.

`active_consumer_ids` is empty when the frame has no active
references (allowed to decommission). When non-empty, the decider
raises `FrameInUseError`.
"""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class DecommissionFrameContext:
    """Snapshot of the Frame's active consumers from projection."""

    active_consumer_ids: tuple[UUID, ...] = field(default_factory=tuple)
