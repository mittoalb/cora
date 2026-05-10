"""Pure decider for the `DiscardSubject` command.

Terminal disposition: `Removed -> Discarded`. Single-source guard
(only `Removed` is a valid prior state). Mirrors `return_subject` /
`store_subject` — three-sibling terminal disposition pattern.

Strict semantics, not idempotent: re-discarding an already-`Discarded`
subject raises rather than no-op.

Invariants:
  - State must not be None -> SubjectNotFoundError
  - State.status must be `Removed` -> SubjectCannotDiscardError(current_status=...)
"""

from datetime import datetime

from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotDiscardError,
    SubjectDiscarded,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features.discard_subject.command import DiscardSubject


def decide(
    state: Subject | None,
    command: DiscardSubject,
    *,
    now: datetime,
) -> list[SubjectDiscarded]:
    """Decide the events produced by discarding an existing subject."""
    if state is None:
        raise SubjectNotFoundError(command.subject_id)
    if state.status is not SubjectStatus.REMOVED:
        raise SubjectCannotDiscardError(state.id, current_status=state.status)
    return [SubjectDiscarded(subject_id=state.id, occurred_at=now)]
