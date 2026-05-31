"""Pure decider for the `UpdateFramePlacement` command.

Pure function: given the current Frame state (loaded by the factory
handler) and an `UpdateFramePlacement` command, returns the events to append.
Returns `[]` for the no-op-on-unchanged case (idempotent contract).

## Invariants

  - State must not be None -> FrameNotFoundError.
  - Status must be Active -> FrameCannotUpdateError (reason: status
    mismatch).
  - Frame must be a child frame (placement_relative_to_parent is not
    None at the aggregate level) -> FrameCannotUpdateError (reason:
    root frame has no placement to update).
  - The new placement's `parent_frame` field must equal the Frame's
    current `parent_frame_id` (you cannot reparent via
    update_frame_placement; that would require a separate
    reparent_frame slice). -> InvalidFrameRootError.
  - When `new_placement == current_placement`, return `[]` (no-op).
"""

from datetime import datetime

from cora.equipment.aggregates.frame import (
    Frame,
    FrameCannotUpdateError,
    FrameNotFoundError,
    FramePlacementUpdated,
    FrameStatus,
    InvalidFrameRootError,
)
from cora.equipment.features.update_frame_placement.command import UpdateFramePlacement


def decide(
    state: Frame | None,
    command: UpdateFramePlacement,
    *,
    now: datetime,
) -> list[FramePlacementUpdated]:
    """Decide the events produced by updating a frame's placement.

    Invariants:
      - State must not be None -> FrameNotFoundError
      - Status must be Active -> FrameCannotUpdateError (status mismatch)
      - Frame must be a child frame (placement_relative_to_parent
        is not None) -> FrameCannotUpdateError (root frame)
      - `new_placement.parent_frame == state.parent_frame_id`
        (update_frame_placement cannot reparent) -> InvalidFrameRootError
      - No-op on unchanged: `new_placement == current_placement`
        returns `[]` (idempotent contract).
    """
    if state is None:
        raise FrameNotFoundError(command.frame_id)
    if state.status is not FrameStatus.ACTIVE:
        msg = (
            f"currently in status {state.status.value}, update requires {FrameStatus.ACTIVE.value}"
        )
        raise FrameCannotUpdateError(state.id, msg)
    if state.placement_relative_to_parent is None:
        msg = (
            "root frame has no placement_relative_to_parent; "
            "update_frame_placement is only valid on child frames"
        )
        raise FrameCannotUpdateError(state.id, msg)
    if command.new_placement.parent_frame != state.parent_frame_id:
        msg = (
            f"new_placement.parent_frame ({command.new_placement.parent_frame}) "
            f"must equal Frame.parent_frame_id ({state.parent_frame_id}); "
            "update_frame_placement cannot reparent"
        )
        raise InvalidFrameRootError(msg)
    if command.new_placement == state.placement_relative_to_parent:
        return []
    return [
        FramePlacementUpdated(
            frame_id=state.id,
            new_placement=command.new_placement,
            survey=command.survey,
            occurred_at=now,
        )
    ]
