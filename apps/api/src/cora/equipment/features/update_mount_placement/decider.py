"""Pure decider for the `UpdateMountPlacement` command.

Pure function: given the current Mount state (loaded by the factory
handler) and an `UpdateMountPlacement` command, returns the events to
append. Returns `[]` for the no-op-on-unchanged case (idempotent
contract via make_mount_update_handler).

## Invariants:

  - State must not be None -> MountNotFoundError.
  - Status must be Active -> MountCannotUpdateError (status mismatch).
  - new_placement.parent_frame MUST equal the current
    placement.parent_frame (update_mount_placement cannot reparent;
    that would require a separate reparent slice). -> MountCannotUpdateError.
  - new_placement == current_placement -> [] (no-op).
"""

from datetime import datetime

from cora.equipment.aggregates.mount import (
    Mount,
    MountCannotUpdateError,
    MountNotFoundError,
    MountPlacementUpdated,
    MountStatus,
)
from cora.equipment.features.update_mount_placement.command import UpdateMountPlacement


def decide(
    state: Mount | None,
    command: UpdateMountPlacement,
    *,
    now: datetime,
) -> list[MountPlacementUpdated]:
    """Decide the events produced by updating a mount's placement."""
    if state is None:
        raise MountNotFoundError(command.mount_id)
    if state.status is not MountStatus.ACTIVE:
        msg = (
            f"currently in status {state.status.value}, "
            f"update_mount_placement requires {MountStatus.ACTIVE.value}"
        )
        raise MountCannotUpdateError(state.id, msg)
    if command.new_placement.parent_frame != state.placement.parent_frame:
        msg = (
            f"new_placement.parent_frame ({command.new_placement.parent_frame}) "
            f"must equal Mount's current placement.parent_frame "
            f"({state.placement.parent_frame}); update_mount_placement cannot reparent"
        )
        raise MountCannotUpdateError(state.id, msg)
    if command.new_placement == state.placement:
        return []
    return [
        MountPlacementUpdated(
            mount_id=state.id,
            new_placement=command.new_placement,
            survey=command.survey,
            occurred_at=now,
        )
    ]
