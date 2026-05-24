"""Pure decider for the `SubmitClearance` command.

Single-source transition: `Defined -> Submitted`. Strict-not-
idempotent: re-submitting an already-Submitted clearance raises.

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `Defined` -> `ClearanceCannotSubmitError`
"""

from datetime import datetime

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotSubmitError,
    ClearanceNotFoundError,
    ClearanceStatus,
    ClearanceSubmitted,
)
from cora.safety.features.submit_clearance.command import SubmitClearance

_SUBMITTABLE_STATUSES: tuple[ClearanceStatus, ...] = (ClearanceStatus.DEFINED,)


def decide(
    state: Clearance | None,
    command: SubmitClearance,
    *,
    now: datetime,
) -> list[ClearanceSubmitted]:
    """Decide the events produced by submitting a Defined clearance.

    Invariants:
      - State must not be None -> ClearanceNotFoundError
      - Current status must be Defined
        -> ClearanceCannotSubmitError
    """
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status not in _SUBMITTABLE_STATUSES:
        raise ClearanceCannotSubmitError(state.id, state.status)

    return [ClearanceSubmitted(clearance_id=state.id, occurred_at=now)]
