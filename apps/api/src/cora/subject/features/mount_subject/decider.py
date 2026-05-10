"""Pure decider for the `MountSubject` command.

Update-style decider: receives the rebuilt `Subject` state (folded
from the loaded event stream) and returns the events to append. No
I/O.

Invariants:
  - State must not be None (subject must exist) -> SubjectNotFoundError
  - State must be in `Received` (the only state from which mount is
    valid) -> SubjectCannotMountError(current_status=...)

Strict semantics, not idempotent: mounting an already-mounted (or
otherwise non-Received) subject raises `SubjectCannotMountError`.
Idempotency-Key already provides retry safety; the domain stays
explicit. Same precedent as `deactivate_actor.decide` raising
`ActorAlreadyDeactivatedError`.

Unlike the create-style register_subject decider, no `new_id` is
injected (we operate on an existing aggregate whose id the command
already carries). `now` is still injected from the Clock port at
handler time.
"""

from datetime import datetime

from cora.subject.aggregates.subject import (
    Subject,
    SubjectCannotMountError,
    SubjectMounted,
    SubjectNotFoundError,
    SubjectStatus,
)
from cora.subject.features.mount_subject.command import MountSubject


def decide(
    state: Subject | None,
    command: MountSubject,
    *,
    now: datetime,
) -> list[SubjectMounted]:
    """Decide the events produced by mounting an existing subject."""
    if state is None:
        raise SubjectNotFoundError(command.subject_id)
    if state.status is not SubjectStatus.RECEIVED:
        raise SubjectCannotMountError(state.id, current_status=state.status)
    return [SubjectMounted(subject_id=state.id, occurred_at=now)]
