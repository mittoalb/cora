"""The `BeginReviewClearance` command -- intent dataclass for this slice.

`first_reviewer_role` is the facility-vocabulary label for the first
step in the review chain (e.g., 'BeamlineScientist', 'LocalContact').
Captured for audit clarity; subsequent steps land via
`record_review_step_clearance`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class BeginReviewClearance:
    """Begin reviewing a Submitted clearance (`Submitted -> UnderReview`)."""

    clearance_id: UUID
    first_reviewer_role: str
