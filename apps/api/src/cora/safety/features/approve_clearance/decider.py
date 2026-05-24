"""Pure decider for the `ApproveClearance` command.

Single-source transition: `UnderReview -> Approved`. Strict-not-
idempotent.

Approval requires that the TERMINAL (last) step in the review chain
has `decision == 'Approved'`. The `append_clearance_review_step`
slice populates the chain step-by-step; this slice's invariant
ensures the most recent reviewer's decision was Approved. An
[Approved, Rejected] chain refuses approve even though it contains an
Approved step somewhere, modelling facilities like DESY DOOR where
any reviewer downstream can veto.

Optional `valid_from` / `valid_until` override defaults set at
register time. Validity-window invariant (valid_from < valid_until
when both provided) is re-enforced here for the same reason as
register: zero-duration windows can never be active.

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `UnderReview` -> `ClearanceCannotApproveError`
  - Terminal review step has decision='Approved' ->
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

_APPROVABLE_STATUSES: tuple[ClearanceStatus, ...] = (ClearanceStatus.UNDER_REVIEW,)


def decide(
    state: Clearance | None,
    command: ApproveClearance,
    *,
    now: datetime,
) -> list[ClearanceApproved]:
    """Decide the events produced by approving an UnderReview clearance.

    Invariants:
      - State must not be None -> ClearanceNotFoundError
      - Current status must be UnderReview
        -> ClearanceCannotApproveError
      - Terminal review step must have decision='Approved'
        -> ClearanceCannotApproveError
      - valid_from must be strictly less than valid_until (when both
        provided) -> InvalidClearanceValidityWindowError
    """
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status not in _APPROVABLE_STATUSES:
        raise ClearanceCannotApproveError(state.id, current_status=state.status)

    if not state.review_steps or state.review_steps[-1].decision != "Approved":
        raise ClearanceCannotApproveError(
            state.id,
            reason="terminal review step has no decision='Approved'",
        )

    if (
        command.valid_from is not None
        and command.valid_until is not None
        and command.valid_from >= command.valid_until
    ):
        raise InvalidClearanceValidityWindowError(command.valid_from, command.valid_until)

    return [
        ClearanceApproved(
            clearance_id=state.id,
            valid_from=command.valid_from,
            valid_until=command.valid_until,
            occurred_at=now,
        )
    ]
