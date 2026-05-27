"""Pure decider for the `ArriveVisit` command.

Single-source transition: `Planned -> Arrived`. Strict-not-idempotent
(re-arriving an already-Arrived visit raises).
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitArrived,
    VisitCannotTransitionError,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.arrive_visit.command import ArriveVisit

_PERMITTED: tuple[VisitStatus, ...] = (VisitStatus.PLANNED,)
_TRANSITION = "arrive"


def decide(
    state: Visit | None,
    command: ArriveVisit,
    *,
    now: datetime,
) -> list[VisitArrived]:
    """Decide events for arriving at a Planned Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be Planned -> VisitCannotTransitionError
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
    return [VisitArrived(visit_id=state.id, occurred_at=now)]
