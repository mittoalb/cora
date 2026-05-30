"""Pure decider for the `RegisterFrame` command.

Pure function: given the current Frame state (None for a fresh
stream) and a `RegisterFrame` command, returns the events to append.
No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.

## Root-vs-child invariant

The "both together or both None" rule:
  - Root frame: `parent_frame_id is None` AND
    `placement_relative_to_parent is None`.
  - Child frame: both non-None, AND
    `placement_relative_to_parent.parent_frame == parent_frame_id`
    (the embedded Placement points at the same parent that the
    Frame declares).

Three failure modes folded into `InvalidFrameRootError`:
  1. `parent_frame_id is None` but `placement_relative_to_parent is
     not None` (root frame can't carry a placement).
  2. `parent_frame_id is not None` but
     `placement_relative_to_parent is None` (child frame missing its
     placement).
  3. Both non-None but `placement.parent_frame != parent_frame_id`
     (placement points at a different frame than the Frame declares).

Eventual-consistency stance: the decider does NOT verify the
referenced parent Frame exists in the event store. Cycle defense
(walking the parent chain for cycles) lives at the handler level
when a `frame_children` projection is available; the decider trusts
its inputs.

Name uniqueness within parent scope (`(parent_frame_id, name)`) is
enforced by the handler's projection precondition, NOT by this
decider.
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates.frame import (
    Frame,
    FrameAlreadyExistsError,
    FrameName,
    FrameRegistered,
    InvalidFrameRootError,
)
from cora.equipment.features.register_frame.command import RegisterFrame


def decide(
    state: Frame | None,
    command: RegisterFrame,
    *,
    now: datetime,
    new_id: UUID,
) -> list[FrameRegistered]:
    """Decide the events produced by registering a new frame.

    Invariants:
      - State must be None (genesis-only) -> FrameAlreadyExistsError
      - Name must be valid -> InvalidFrameNameError (via FrameName VO)
      - Root-vs-child invariant: both `parent_frame_id` and
        `placement_relative_to_parent` together, or both None
        -> InvalidFrameRootError
      - When child: `placement.parent_frame == parent_frame_id`
        -> InvalidFrameRootError
    """
    if state is not None:
        raise FrameAlreadyExistsError(state.id)

    name = FrameName(command.name)

    parent_frame_id = command.parent_frame_id
    placement = command.placement_relative_to_parent

    if parent_frame_id is None and placement is not None:
        msg = (
            "Root frame (parent_frame_id=None) cannot carry a "
            "placement_relative_to_parent (got a non-None Placement)"
        )
        raise InvalidFrameRootError(msg)
    if parent_frame_id is not None and placement is None:
        msg = (
            f"Child frame (parent_frame_id={parent_frame_id}) must carry "
            "a placement_relative_to_parent (got None)"
        )
        raise InvalidFrameRootError(msg)
    if (
        parent_frame_id is not None
        and placement is not None
        and placement.parent_frame != parent_frame_id
    ):
        msg = (
            f"Placement.parent_frame ({placement.parent_frame}) must equal "
            f"the Frame's parent_frame_id ({parent_frame_id})"
        )
        raise InvalidFrameRootError(msg)

    return [
        FrameRegistered(
            frame_id=new_id,
            name=name.value,
            parent_frame_id=parent_frame_id,
            placement_relative_to_parent=placement,
            occurred_at=now,
        )
    ]
