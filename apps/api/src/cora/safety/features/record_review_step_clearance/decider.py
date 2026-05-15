"""Pure decider for the `RecordReviewStepClearance` command.

Append-only-into-tuple, no status change.

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `UnderReview` ->
    `ClearanceCannotRecordReviewStepError`
  - `step_index` must equal `len(state.reviewers)` ->
    `InvalidClearanceReviewStepIndexError`
  - `role` validated 1-50 chars after trim ->
    `InvalidClearanceReviewerRoleError`
  - `notes` validated 0-2000 chars after trim ->
    `InvalidClearanceReviewerNotesError`
  - `decision` membership in `{Approved, Rejected, RequestedChanges}`
    is enforced at the API layer (Pydantic Literal); deciders trust
    typed input
"""

from datetime import datetime

from cora.infrastructure.bounded_text import validate_bounded_text
from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotRecordReviewStepError,
    ClearanceNotFoundError,
    ClearanceReviewStepRecorded,
    ClearanceStatus,
    InvalidClearanceReviewerNotesError,
    InvalidClearanceReviewerRoleError,
    InvalidClearanceReviewStepIndexError,
)
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REVIEWER_NOTES_MAX_LENGTH,
    CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
)
from cora.safety.features.record_review_step_clearance.command import (
    RecordReviewStepClearance,
)


def decide(
    state: Clearance | None,
    command: RecordReviewStepClearance,
    *,
    now: datetime,
) -> list[ClearanceReviewStepRecorded]:
    """Decide the events produced by appending one reviewer step."""
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status is not ClearanceStatus.UNDER_REVIEW:
        raise ClearanceCannotRecordReviewStepError(state.id, state.status)

    expected = len(state.reviewers)
    if command.step_index != expected:
        raise InvalidClearanceReviewStepIndexError(expected=expected, got=command.step_index)

    role = validate_bounded_text(
        command.role,
        max_length=CLEARANCE_REVIEWER_ROLE_MAX_LENGTH,
        error_class=InvalidClearanceReviewerRoleError,
    )

    notes: str | None
    if command.notes is None:
        notes = None
    else:
        trimmed_notes = command.notes.strip()
        if len(trimmed_notes) > CLEARANCE_REVIEWER_NOTES_MAX_LENGTH:
            raise InvalidClearanceReviewerNotesError(command.notes)
        notes = trimmed_notes if trimmed_notes else None

    return [
        ClearanceReviewStepRecorded(
            clearance_id=state.id,
            step_index=command.step_index,
            role=role,
            actor_id=command.actor_id,
            decision=command.decision,
            decided_at=command.decided_at,
            notes=notes,
            occurred_at=now,
        )
    ]
