"""Pure decider for the `DecommissionFrame` command.

Pure function: given the current Frame state, the loaded consumer
context, and the command, returns the events to append. No I/O, no
awaits, no side effects.

## Invariants

  - State must not be None -> FrameNotFoundError.
  - Status must be Active -> FrameCannotDecommissionError (reason:
    status mismatch).
  - `context.active_consumer_ids` must be empty -> FrameInUseError.
    The handler is responsible for loading the consumer list from
    the `frame_consumers` projection BEFORE calling decide; the
    decider trusts what it receives.
"""

from datetime import datetime

from cora.equipment.aggregates.frame import (
    Frame,
    FrameCannotDecommissionError,
    FrameDecommissioned,
    FrameInUseError,
    FrameNotFoundError,
    FrameStatus,
)
from cora.equipment.features.decommission_frame.command import DecommissionFrame
from cora.equipment.features.decommission_frame.context import DecommissionFrameContext


def decide(
    state: Frame | None,
    command: DecommissionFrame,
    *,
    context: DecommissionFrameContext,
    now: datetime,
) -> list[FrameDecommissioned]:
    """Decide the events produced by decommissioning an existing frame.

    Invariants:
      - State must not be None -> FrameNotFoundError
      - Status must be Active -> FrameCannotDecommissionError
        (status mismatch; double-decommission rejected)
      - `context.active_consumer_ids` must be empty
        -> FrameInUseError (handler loads consumers from the
        frame_consumers projection BEFORE calling decide).
    """
    if state is None:
        raise FrameNotFoundError(command.frame_id)
    if state.status is not FrameStatus.ACTIVE:
        msg = (
            f"currently in status {state.status.value}, "
            f"decommission requires {FrameStatus.ACTIVE.value}"
        )
        raise FrameCannotDecommissionError(state.id, msg)
    if context.active_consumer_ids:
        raise FrameInUseError(state.id, context.active_consumer_ids)
    return [
        FrameDecommissioned(
            frame_id=state.id,
            reason=command.reason,
            occurred_at=now,
        )
    ]
