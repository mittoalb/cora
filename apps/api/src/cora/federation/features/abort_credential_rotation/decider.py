"""Pure decider for the `AbortCredentialRotation` command.

Single-source transition: `Rotating -> Active`. Strict-not-idempotent
(matches the Calibration / Clearance / Supply / Permit precedent):
aborting a rotation on a credential that is not in `Rotating` status
raises `CredentialCannotRotateError`.

`rotation_aborted_by_actor_id` is handler-injected from the request
envelope's `principal_id` per the non-determinism principle (capture,
don't recompute). The decider is pure: state + command + injected
non-determinism in, events out.

Pending refs are NOT promoted: the evolver clears
`rotation_pending_secret_ref` / `rotation_pending_public_material_ref`
on apply and leaves the current `secret_ref` /
`public_material_ref` unchanged. This is the safe escape hatch when
a rotation cannot complete (peer refused new material, SecretStore
generation failed, operator changed their mind).

## Validation

  - State must not be None (credential must exist)
    -> CredentialNotFoundError
  - Current status must be `Rotating`
    -> CredentialCannotRotateError(attempted='abort_rotation')
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.credential import (
    Credential,
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialRotationAborted,
    CredentialStatus,
)
from cora.federation.features.abort_credential_rotation.command import (
    AbortCredentialRotation,
)


def decide(
    state: Credential | None,
    command: AbortCredentialRotation,
    *,
    now: datetime,
    rotation_aborted_by_actor_id: UUID,
) -> list[CredentialRotationAborted]:
    """Decide the events produced by aborting a credential rotation.

    Invariants:
      - State must not be None -> CredentialNotFoundError
      - Current status must be Rotating
        -> CredentialCannotRotateError
    """
    if state is None:
        raise CredentialNotFoundError(command.credential_id)
    if state.status is not CredentialStatus.ROTATING:
        raise CredentialCannotRotateError(
            state.id,
            state.status,
            "abort_rotation",
        )

    return [
        CredentialRotationAborted(
            credential_id=state.id,
            rotation_aborted_by_actor_id=rotation_aborted_by_actor_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
