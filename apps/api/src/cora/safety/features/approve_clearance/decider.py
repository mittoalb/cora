"""Pure decider for the `ApproveClearance` command.

Single-source transition: `UnderReview -> Approved`. Strict-not-
idempotent.

Approval requires that at least ONE step in the review_steps chain has
`decision == 'Approved'`. The `append_clearance_review_step` slice
populates the chain step-by-step; this slice's invariant ensures we
don't approve based on an empty or all-rejected chain. Per the
design memo's "approve_clearance decider" §"review_steps must have one
Approved step" rejection.

Optional `valid_from` / `valid_until` override defaults set at
register time. Validity-window invariant (valid_from < valid_until
when both provided) is re-enforced here for the same reason as
register: zero-duration windows can never be active.

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `UnderReview` -> `ClearanceCannotApproveError`
  - At least one reviewer step has decision='Approved' ->
    `ClearanceCannotApproveError(reason=...)`
  - `valid_from >= valid_until` (when both provided) ->
    `InvalidClearanceValidityWindowError`
"""

from datetime import datetime

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceApproved,
    ClearanceCannotApproveError,
    ClearanceNotFoundError,
    ClearanceStatus,
    InvalidClearanceValidityWindowError,
)
from cora.safety.features.approve_clearance.command import ApproveClearance


def decide(
    state: Clearance | None,
    command: ApproveClearance,
    *,
    now: datetime,
) -> list[ClearanceApproved]:
    """Decide the events produced by approving an UnderReview clearance."""
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status is not ClearanceStatus.UNDER_REVIEW:
        raise ClearanceCannotApproveError(state.id, current_status=state.status)

    if not any(step.decision == "Approved" for step in state.review_steps):
        raise ClearanceCannotApproveError(state.id, reason="no approving reviewer step recorded")

    if (
        command.valid_from is not None
        and command.valid_until is not None
        and command.valid_from >= command.valid_until
    ):
        raise InvalidClearanceValidityWindowError(command.valid_from, command.valid_until)

    return [
        ClearanceApproved(
            clearance_id=state.id,
            approving_actor_id=command.approving_actor_id,
            valid_from=command.valid_from,
            valid_until=command.valid_until,
            occurred_at=now,
        )
    ]
