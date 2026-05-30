"""Pure decider for the `ResumePermit` command.

Single-source transition: `Suspended -> Active`. Strict-not-
idempotent: resuming an already-Active (or Defined / Revoked)
permit raises `PermitCannotResumeError`.

Distinct from `activate_permit` which exits `Defined -> Active`:
the two transitions target the same status but carry different
audit semantics (first activation vs resume-after-suspend) and
emit different event types (`PermitActivated` vs `PermitResumed`).

## Validation

  - State must not be None (permit must exist) -> PermitNotFoundError
  - Current status must be `Suspended` -> PermitCannotResumeError

The handler-injected `resumed_by_actor_id` denorms the principal-id
on the emitted event payload per the Calibration / Clearance
precedent.
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.permit import (
    Permit,
    PermitCannotResumeError,
    PermitNotFoundError,
    PermitResumed,
    PermitStatus,
)
from cora.federation.features.resume_permit.command import ResumePermit


def decide(
    state: Permit | None,
    command: ResumePermit,
    *,
    now: datetime,
    resumed_by_actor_id: UUID,
) -> list[PermitResumed]:
    """Decide the events produced by resuming a Suspended Permit.

    Invariants:
      - State must not be None -> PermitNotFoundError
      - Current status must be Suspended -> PermitCannotResumeError
    """
    if state is None:
        raise PermitNotFoundError(command.permit_id)
    if state.status is not PermitStatus.SUSPENDED:
        raise PermitCannotResumeError(state.id, state.status)

    return [
        PermitResumed(
            permit_id=state.id,
            resumed_by_actor_id=resumed_by_actor_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
