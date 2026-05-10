"""Subject aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.subject.features.<verb>_subject/` and import from here for
state and event types.
"""

from cora.subject.aggregates.subject.events import (
    SubjectEvent,
    SubjectRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.subject.aggregates.subject.evolver import evolve, fold
from cora.subject.aggregates.subject.read import load_subject
from cora.subject.aggregates.subject.state import (
    SUBJECT_NAME_MAX_LENGTH,
    InvalidSubjectNameError,
    Subject,
    SubjectAlreadyExistsError,
    SubjectName,
    SubjectStatus,
)

__all__ = [
    "SUBJECT_NAME_MAX_LENGTH",
    "InvalidSubjectNameError",
    "Subject",
    "SubjectAlreadyExistsError",
    "SubjectEvent",
    "SubjectName",
    "SubjectRegistered",
    "SubjectStatus",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_subject",
    "to_payload",
]
