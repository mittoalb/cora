"""Pure decider for the `ActivatePermit` command.

Single-source transition: `Defined -> Active`. Strict-not-idempotent
(matches the Calibration / Clearance / Supply precedent): re-activating
an already-Active permit raises `PermitCannotActivateError`.

`activated_by_actor_id` is handler-injected from the request envelope's
`principal_id` per the non-determinism principle (capture, don't
recompute). The decider is pure: state + command + injected
non-determinism in, events out.

## Validation

  - State must not be None (permit must exist) -> PermitNotFoundError
  - Current status must be `Defined` -> PermitCannotActivateError
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.permit import (
    Permit,
    PermitActivated,
    PermitCannotActivateError,
    PermitNotFoundError,
    PermitStatus,
)
from cora.federation.features.activate_permit.command import ActivatePermit


def decide(
    state: Permit | None,
    command: ActivatePermit,
    *,
    now: datetime,
    activated_by_actor_id: UUID,
) -> list[PermitActivated]:
    """Decide the events produced by activating a Defined permit.

    Invariants:
      - State must not be None -> PermitNotFoundError
      - Current status must be Defined
        -> PermitCannotActivateError
    """
    if state is None:
        raise PermitNotFoundError(command.permit_id)
    if state.status is not PermitStatus.DEFINED:
        raise PermitCannotActivateError(state.id, state.status)

    return [
        PermitActivated(
            permit_id=state.id,
            activated_by_actor_id=activated_by_actor_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
