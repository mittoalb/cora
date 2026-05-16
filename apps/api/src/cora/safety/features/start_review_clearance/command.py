"""The `StartReviewClearance` command -- intent dataclass for this slice.

`first_reviewer_role` is the facility-vocabulary label for the first
step in the review chain (e.g., 'BeamlineScientist', 'LocalContact').
Captured for audit clarity; subsequent steps land via
`append_clearance_review_step`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StartReviewClearance:
    """Begin reviewing a Submitted clearance (`Submitted -> UnderReview`)."""

    clearance_id: UUID
    first_reviewer_role: str
