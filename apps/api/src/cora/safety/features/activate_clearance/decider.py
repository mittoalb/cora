"""Pure decider for the `ActivateClearance` command.

Single-source transition: `Approved -> Active`. Strict-not-idempotent.

## Validation

  - State must not be None -> `ClearanceNotFoundError`
  - Current status must be `Approved` -> `ClearanceCannotActivateError`
"""

from datetime import datetime

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceActivated,
    ClearanceCannotActivateError,
    ClearanceNotFoundError,
    ClearanceStatus,
)
from cora.safety.features.activate_clearance.command import ActivateClearance


def decide(
    state: Clearance | None,
    command: ActivateClearance,
    *,
    now: datetime,
) -> list[ClearanceActivated]:
    """Decide the events produced by activating an Approved clearance."""
    if state is None:
        raise ClearanceNotFoundError(command.clearance_id)
    if state.status is not ClearanceStatus.APPROVED:
        raise ClearanceCannotActivateError(state.id, state.status)

    return [ClearanceActivated(clearance_id=state.id, occurred_at=now)]
