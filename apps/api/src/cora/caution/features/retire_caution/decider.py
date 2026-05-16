"""Pure decider for the `RetireCaution` command.

Single-source transition: `Active -> Retired`. Strict-not-idempotent.
Terminal-good: retired cautions cannot be revived.

## Validation

  - State must not be None -> `CautionNotFoundError`
  - Current status must be `Active` -> `CautionCannotRetireError`
  - `reason` enum-membership is validated by Pydantic at the API
    boundary; this decider trusts its typed `CautionRetireReason`
    input.
"""

from datetime import datetime

from cora.caution.aggregates.caution import (
    Caution,
    CautionCannotRetireError,
    CautionNotFoundError,
    CautionRetired,
    CautionStatus,
)
from cora.caution.features.retire_caution.command import RetireCaution

_RETIRABLE_STATUSES: tuple[CautionStatus, ...] = (CautionStatus.ACTIVE,)


def decide(
    state: Caution | None,
    command: RetireCaution,
    *,
    now: datetime,
) -> list[CautionRetired]:
    """Decide the events produced by retiring an Active caution."""
    if state is None:
        raise CautionNotFoundError(command.caution_id)
    if state.status not in _RETIRABLE_STATUSES:
        raise CautionCannotRetireError(state.id, state.status)

    return [
        CautionRetired(
            caution_id=state.id,
            reason=command.reason.value,
            occurred_at=now,
        )
    ]
