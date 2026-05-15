"""Pure decider for the `RejectClearance` command.

Single-source transition: `UnderReview -> Rejected`. Strict-not-
idempotent. Terminal-bad: rejected clearances cannot be revived; a
new Clearance must be registered if the operator wants to retry.

The rejecting actor's id is captured from the handler's `principal_id`
(injected by the cross-BC update-handler factory). That keeps the
audit truth single-sourced (the principal calling the slice IS the
rejecting reviewer).

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `UnderReview` -> `ClearanceCannotRejectError`
  - `reason` validated 1-500 chars after trim ->
    `InvalidClearanceRejectReasonError`
"""

from datetime import datetime

from cora.infrastructure.bounded_text import validate_bounded_text
from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotRejectError,
    ClearanceNotFoundError,
    ClearanceRejected,
    ClearanceStatus,
    InvalidClearanceRejectReasonError,
)
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_REJECT_REASON_MAX_LENGTH,
)
from cora.safety.features.reject_clearance.command import RejectClearance


def decide(
    state: Clearance | None,
    command: RejectClearance,
    *,
    now: datetime,
) -> list[ClearanceRejected]:
    """Decide the events produced by rejecting an UnderReview clearance."""
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status is not ClearanceStatus.UNDER_REVIEW:
        raise ClearanceCannotRejectError(state.id, state.status)

    reason = validate_bounded_text(
        command.reason,
        max_length=CLEARANCE_REJECT_REASON_MAX_LENGTH,
        error_class=InvalidClearanceRejectReasonError,
    )

    return [
        ClearanceRejected(
            clearance_id=state.id,
            rejecting_actor_id=command.rejecting_actor_id,
            reason=reason,
            occurred_at=now,
        )
    ]
