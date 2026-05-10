"""Subject aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.subject.features.<verb>_subject/` and import from here for
state and event types.
"""

from cora.subject.aggregates.subject.events import (
    SubjectDiscarded,
    SubjectEvent,
    SubjectMeasured,
    SubjectMounted,
    SubjectRegistered,
    SubjectRemoved,
    SubjectReturned,
    SubjectStored,
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
    SubjectCannotDiscardError,
    SubjectCannotMeasureError,
    SubjectCannotMountError,
    SubjectCannotRemoveError,
    SubjectCannotReturnError,
    SubjectCannotStoreError,
    SubjectName,
    SubjectNotFoundError,
    SubjectStatus,
)

__all__ = [
    "SUBJECT_NAME_MAX_LENGTH",
    "InvalidSubjectNameError",
    "Subject",
    "SubjectAlreadyExistsError",
    "SubjectCannotDiscardError",
    "SubjectCannotMeasureError",
    "SubjectCannotMountError",
    "SubjectCannotRemoveError",
    "SubjectCannotReturnError",
    "SubjectCannotStoreError",
    "SubjectDiscarded",
    "SubjectEvent",
    "SubjectMeasured",
    "SubjectMounted",
    "SubjectName",
    "SubjectNotFoundError",
    "SubjectRegistered",
    "SubjectRemoved",
    "SubjectReturned",
    "SubjectStatus",
    "SubjectStored",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_subject",
    "to_payload",
]
