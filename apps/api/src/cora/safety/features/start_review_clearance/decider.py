"""Pure decider for the `StartReviewClearance` command.

Single-source transition: `Submitted -> UnderReview`. Strict-not-
idempotent.

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `Submitted` -> `ClearanceCannotStartReviewError`
  - `first_reviewer_role` validated 1-50 chars after trim ->
    `InvalidClearanceReviewerRoleError` (free-form facility vocabulary;
    role-taxonomy closed-StrEnum promotion deferred per design memo
    watch item)
"""

from datetime import datetime

from cora.infrastructure.bounded_text import validate_bounded_text
from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotStartReviewError,
    ClearanceNotFoundError,
    ClearanceReviewStarted,
    ClearanceStatus,
    InvalidClearanceReviewerRoleError,
)
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.start_review_clearance.command import StartReviewClearance


def decide(
    state: Clearance | None,
    command: StartReviewClearance,
    *,
    now: datetime,
) -> list[ClearanceReviewStarted]:
    """Decide the events produced by beginning review on a Submitted clearance."""
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status is not ClearanceStatus.SUBMITTED:
        raise ClearanceCannotStartReviewError(state.id, state.status)

    role = validate_bounded_text(
        command.first_reviewer_role,
        max_length=CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
        error_class=InvalidClearanceReviewerRoleError,
    )

    return [
        ClearanceReviewStarted(
            clearance_id=state.id,
            first_reviewer_role=role,
            occurred_at=now,
        )
    ]
