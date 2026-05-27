"""Pure decider for the `StartVisit` command.

Single-source transition: `Arrived -> InProgress`. Strict-not-idempotent.
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitCannotTransitionError,
    VisitNotFoundError,
    VisitStarted,
    VisitStatus,
)
from cora.trust.features.start_visit.command import StartVisit

_PERMITTED: tuple[VisitStatus, ...] = (VisitStatus.ARRIVED,)
_TRANSITION = "start"


def decide(
    state: Visit | None,
    command: StartVisit,
    *,
    now: datetime,
) -> list[VisitStarted]:
    """Decide events for starting an Arrived Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be Arrived -> VisitCannotTransitionError
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
    return [VisitStarted(visit_id=state.id, occurred_at=now)]
