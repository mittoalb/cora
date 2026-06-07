"""Pure decider for the `CompleteCredentialRotation` command.

Single-source transition: `Rotating -> Active`. Strict-not-idempotent
(matches the Calibration / Clearance / Supply / Permit precedent):
completing a rotation on a credential that is not in `Rotating` status
raises `CredentialCannotRotateError`.

`rotation_completed_by` is handler-injected from the request
envelope's `principal_id` per the non-determinism principle (capture,
don't recompute). The decider is pure: state + command + injected
non-determinism in, events out.

## Validation

  - State must not be None (credential must exist)
    -> CredentialNotFoundError
  - Current status must be `Rotating`
    -> CredentialCannotRotateError(attempted='complete_rotation')
  - `state.rotation_pending_secret_ref` must not be None
    -> CredentialCannotRotateError(attempted='complete_rotation')

The pending-ref-present guard is belt-and-braces: the evolver only
sets `Rotating` status alongside populated pending refs, but the
decider still asserts the invariant locally so a malformed event log
fails loud rather than silently promoting `None` to current.
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.credential import (
    Credential,
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialRotationCompleted,
    CredentialStatus,
)
from cora.federation.features.complete_credential_rotation.command import (
    CompleteCredentialRotation,
)


def decide(
    state: Credential | None,
    command: CompleteCredentialRotation,
    *,
    now: datetime,
    rotation_completed_by: UUID,
) -> list[CredentialRotationCompleted]:
    """Decide the events produced by completing a credential rotation.

    Invariants:
      - State must not be None -> CredentialNotFoundError
      - Current status must be Rotating
        -> CredentialCannotRotateError
      - Pending secret ref must be populated
        -> CredentialCannotRotateError
    """
    if state is None:
        raise CredentialNotFoundError(command.credential_id)
    if state.status is not CredentialStatus.ROTATING:
        raise CredentialCannotRotateError(
            state.id,
            state.status,
            "complete_rotation",
        )
    if state.rotation_pending_secret_ref is None:
        raise CredentialCannotRotateError(
            state.id,
            state.status,
            "complete_rotation",
        )

    return [
        CredentialRotationCompleted(
            credential_id=state.id,
            rotation_completed_by=rotation_completed_by,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
