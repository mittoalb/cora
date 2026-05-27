"""The `ResumeVisit` command -- intent dataclass.

Pair of `hold_visit`: returns an OnHold visit to InProgress. The
`last_status_reason` from the prior Hold is preserved across resume
(audit breadcrumb: "why was it held before the resume?" stays
readable).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ResumeVisit:
    """Transition OnHold -> InProgress."""

    visit_id: UUID
