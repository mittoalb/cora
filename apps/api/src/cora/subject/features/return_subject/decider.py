"""Pure decider for the `ReturnSubject` command.

Terminal disposition: `Removed -> Returned`. Single-source guard
(only `Removed` is a valid prior state). Mirrors `measure_subject`'s
single-source decider shape.

Strict semantics, not idempotent: re-returning an already-`Returned`
subject raises rather than no-op.

Invariants:
  - State must not be None -> SubjectNotFoundError
  - State.status must be `Removed` -> SubjectCannotReturnError(current_status=...)
"""

from datetime import datetime

from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotReturnError,
    SubjectNotFoundError,
    SubjectReturned,
    SubjectStatus,
)
from cora.subject.features.return_subject.command import ReturnSubject


def decide(
    state: Subject | None,
    command: ReturnSubject,
    *,
    now: datetime,
) -> list[SubjectReturned]:
    """Decide the events produced by returning an existing subject."""
    if state is None:
        raise SubjectNotFoundError(command.subject_id)
    if state.status is not SubjectStatus.REMOVED:
        raise SubjectCannotReturnError(state.id, current_status=state.status)
    return [SubjectReturned(subject_id=state.id, occurred_at=now)]
