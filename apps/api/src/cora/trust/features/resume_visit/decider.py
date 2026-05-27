"""Pure decider for the `ResumeVisit` command.

Single-source transition: `OnHold -> InProgress`. Strict-not-idempotent.
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    Visit,
    VisitCannotTransitionError,
    VisitNotFoundError,
    VisitResumed,
    VisitStatus,
)
from cora.trust.features.resume_visit.command import ResumeVisit

_PERMITTED: tuple[VisitStatus, ...] = (VisitStatus.ON_HOLD,)
_TRANSITION = "resume"


def decide(
    state: Visit | None,
    command: ResumeVisit,
    *,
    now: datetime,
) -> list[VisitResumed]:
    """Decide events for resuming an OnHold Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be OnHold -> VisitCannotTransitionError
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
    return [VisitResumed(visit_id=state.id, occurred_at=now)]
