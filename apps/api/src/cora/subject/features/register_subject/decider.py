"""Pure decider for the `RegisterSubject` command.

Pure function: given the current Subject state (None for a fresh
stream) and a `RegisterSubject` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports.
"""

from datetime import datetime
from uuid import UUID

from cora.subject.aggregates.subject import (
    Subject,
    SubjectAlreadyExistsError,
    SubjectName,
    SubjectRegistered,
)
from cora.subject.features.register_subject.command import RegisterSubject


def decide(
    state: Subject | None,
    command: RegisterSubject,
    *,
    now: datetime,
    new_id: UUID,
) -> list[SubjectRegistered]:
    """Decide the events produced by registering a new subject.

    Invariants:
      - State must be None (genesis-only)
        -> SubjectAlreadyExistsError
      - Name must be valid -> InvalidSubjectNameError
        (via SubjectName VO)
    """
    if state is not None:
        raise SubjectAlreadyExistsError(state.id)
    name = SubjectName(command.name)  # validates + trims; raises InvalidSubjectNameError
    return [
        SubjectRegistered(
            subject_id=new_id,
            name=name.value,
            occurred_at=now,
        )
    ]
