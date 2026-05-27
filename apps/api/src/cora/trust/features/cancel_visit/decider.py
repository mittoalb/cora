"""Pure decider for the `CancelVisit` command.

Multi-source transition: `Planned | Arrived -> Cancelled`. Strict-not-
idempotent. Pre-work cancel only; an InProgress Visit must be Aborted
instead (HL7 v2 A11 vs A13 precedent).
"""

from datetime import datetime

from cora.trust.aggregates.visit import (
    VISIT_REASON_MAX_LENGTH,
    InvalidVisitReasonError,
    Visit,
    VisitCancelled,
    VisitCannotTransitionError,
    VisitNotFoundError,
    VisitStatus,
)
from cora.trust.features.cancel_visit.command import CancelVisit

_PERMITTED: tuple[VisitStatus, ...] = (VisitStatus.PLANNED, VisitStatus.ARRIVED)
_TRANSITION = "cancel"


def decide(
    state: Visit | None,
    command: CancelVisit,
    *,
    now: datetime,
) -> list[VisitCancelled]:
    """Decide events for cancelling a Planned or Arrived Visit.

    Invariants:
      - State must not be None -> VisitNotFoundError
      - Status must be Planned or Arrived -> VisitCannotTransitionError
        (InProgress/OnHold must use abort_visit; terminals refuse)
      - Reason 1-500 chars after trim -> InvalidVisitReasonError
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
    trimmed = command.reason.strip()
    if not trimmed or len(trimmed) > VISIT_REASON_MAX_LENGTH:
        raise InvalidVisitReasonError(command.reason)
    return [VisitCancelled(visit_id=state.id, reason=trimmed, occurred_at=now)]
