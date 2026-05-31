"""Pure decider for the `RevokePermit` command.

Widest-source terminal transition: any non-Revoked status (Defined,
Active, or Suspended) transitions to Revoked. Strict-not-idempotent:
re-revoking an already-Revoked permit raises
`PermitCannotRevokeError` (HTTP 409) per the same convention as
`deregister_supply` / `mark_supply_available`.

`revoked_by_actor_id` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the
emitted `PermitRevoked` event for the audit denorm.

## Validation

  - State must not be None (permit must exist) -> PermitNotFoundError
  - Current status must not be Revoked -> PermitCannotRevokeError
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.permit import (
    Permit,
    PermitCannotRevokeError,
    PermitNotFoundError,
    PermitRevoked,
    PermitStatus,
)
from cora.federation.features.revoke_permit.command import RevokePermit


def decide(
    state: Permit | None,
    command: RevokePermit,
    *,
    now: datetime,
    revoked_by_actor_id: UUID,
) -> list[PermitRevoked]:
    """Decide the events produced by revoking a Permit.

    Invariants:
      - State must not be None -> PermitNotFoundError
      - Current status must not be Revoked
        -> PermitCannotRevokeError
    """
    if state is None:
        raise PermitNotFoundError(command.permit_id)
    if state.status is PermitStatus.REVOKED:
        raise PermitCannotRevokeError(state.id, state.status)

    return [
        PermitRevoked(
            permit_id=state.id,
            revoked_by_actor_id=revoked_by_actor_id,
            occurred_at=now,
            reason=command.reason,
        )
    ]


__all__ = ["decide"]
