"""The `list_subjects` query slice.

Cursor-paginated list of subjects backed by the
`proj_subject_summary` read model that the projection worker keeps
up-to-date. Read-only; no events emitted.
"""

from cora.subject.features.list_subjects.handler import (
    Handler,
    SubjectListPage,
    SubjectSummaryItem,
    bind,
)
from cora.subject.features.list_subjects.query import ListSubjects
from cora.subject.features.list_subjects.route import router

__all__ = [
    "Handler",
    "ListSubjects",
    "SubjectListPage",
    "SubjectSummaryItem",
    "bind",
    "router",
]
