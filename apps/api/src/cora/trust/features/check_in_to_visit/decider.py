"""Pure decider for the `CheckInToVisit` command.

Two-part guard:
  - `Visit.status in {Arrived, InProgress, OnHold}` (presence is
    orthogonal to lifecycle; pre-arrival check-in is rejected per V6
    explicit-gesture lock)
  - No open presence entry already exists for `actor_id` (composite
    uniqueness on `(actor_id, check_out_at IS NULL)`)
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitAlreadyCheckedInError,
    VisitCannotTransitionError,
    VisitCheckedIn,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.check_in_to_visit.command import CheckInToVisit

_PERMITTED: tuple[VisitStatus, ...] = (
    VisitStatus.ARRIVED,
    VisitStatus.IN_PROGRESS,
    VisitStatus.ON_HOLD,
)
_TRANSITION = "check_in"


def decide(
    state: Visit | None,
    command: CheckInToVisit,
    *,
    now: datetime,
) -> list[VisitCheckedIn]:
    """Decide events for checking an actor in to a Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be Arrived / InProgress / OnHold
        -> VisitCannotTransitionError
        (operator must arrive_visit first; presence does not auto-arrive)
      - No open presence entry for this actor -> VisitAlreadyCheckedInError
    """
    if state is None:
        raise VisitNotFoundError(command.visit_id)
    if state.status not in _PERMITTED:
        raise VisitCannotTransitionError(
            visit_id=state.id,
            current_status=state.status,
            requested_transition=_TRANSITION,
            permitted_sources=_PERMITTED,
        )
    open_entry_exists = any(
        e.actor_id == command.actor_id and e.check_out_at is None for e in state.presence_entries
    )
    if open_entry_exists:
        raise VisitAlreadyCheckedInError(visit_id=state.id, actor_id=command.actor_id)
    return [
        VisitCheckedIn(
            visit_id=state.id,
            actor_id=command.actor_id,
            mode=command.mode.value,
            occurred_at=now,
        )
    ]
