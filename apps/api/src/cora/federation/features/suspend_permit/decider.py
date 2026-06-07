"""Pure decider for the `SuspendPermit` command.

Active -> Suspended transition. Strict-not-idempotent: re-suspending
an already-Suspended permit raises (and re-suspending a Defined or
Revoked permit raises) via `PermitCannotSuspendError` -> HTTP 409.

## Validation

  - State must not be None (permit must exist) -> PermitNotFoundError
  - Current status must be `Active` -> PermitCannotSuspendError

## Non-determinism

`now` is injected by the handler ("capture, don't recompute" per
[[project_non_determinism_principle]]). `suspended_by` is
the invoking principal, passed by the handler at decide-time so the
decider stays pure.
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.permit import (
    Permit,
    PermitCannotSuspendError,
    PermitNotFoundError,
    PermitStatus,
    PermitSuspended,
)
from cora.federation.features.suspend_permit.command import SuspendPermit


def decide(
    state: Permit | None,
    command: SuspendPermit,
    *,
    now: datetime,
    suspended_by: UUID,
) -> list[PermitSuspended]:
    """Decide the events produced by suspending an Active Permit.

    Invariants:
      - State must not be None -> PermitNotFoundError
      - Current status must be Active -> PermitCannotSuspendError
    """
    if state is None:
        raise PermitNotFoundError(command.permit_id)
    if state.status is not PermitStatus.ACTIVE:
        raise PermitCannotSuspendError(state.id, state.status)

    return [
        PermitSuspended(
            permit_id=state.id,
            suspended_by=suspended_by,
            occurred_at=now,
            reason=command.reason,
        )
    ]


__all__ = ["decide"]
