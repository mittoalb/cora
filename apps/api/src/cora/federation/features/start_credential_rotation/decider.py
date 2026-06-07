"""Pure decider for the `StartCredentialRotation` command.

Single-source transition: `Active -> Rotating`. Strict-not-idempotent
(matches the Calibration / Clearance / Supply / Permit precedent):
starting a rotation against an already Rotating or Revoked credential
raises `CredentialCannotRotateError`.

`rotation_started_by` is handler-injected from the request
envelope's `principal_id` per the non-determinism principle (capture,
don't recompute). The decider is pure: state + command + injected
non-determinism in, events out.

## Validation

  - State must not be None (credential must exist)
    -> CredentialNotFoundError
  - Current status must be `Active`
    -> CredentialCannotRotateError(attempted="start_rotation")
  - `new_secret_ref` must be non-empty after trimming
    -> InvalidCredentialSecretRefError
  - `new_secret_ref` must differ from the current `secret_ref`
    -> CredentialCannotRotateError(attempted="start_rotation_same_ref")
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.credential import (
    Credential,
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialRotationStarted,
    CredentialStatus,
    InvalidCredentialSecretRefError,
)
from cora.federation.features.start_credential_rotation.command import (
    StartCredentialRotation,
)


def decide(
    state: Credential | None,
    command: StartCredentialRotation,
    *,
    now: datetime,
    rotation_started_by: UUID,
) -> list[CredentialRotationStarted]:
    """Decide the events produced by starting a rotation on an Active credential.

    Invariants:
      - State must not be None -> CredentialNotFoundError
      - Current status must be Active
        -> CredentialCannotRotateError(attempted="start_rotation")
      - new_secret_ref must be non-empty after trimming
        -> InvalidCredentialSecretRefError
      - new_secret_ref must differ from current secret_ref
        -> CredentialCannotRotateError(attempted="start_rotation_same_ref")
    """
    if state is None:
        raise CredentialNotFoundError(command.credential_id)
    if state.status is not CredentialStatus.ACTIVE:
        raise CredentialCannotRotateError(state.id, state.status, "start_rotation")

    pending_secret_ref = command.new_secret_ref.strip()
    if not pending_secret_ref:
        raise InvalidCredentialSecretRefError("new_secret_ref", command.new_secret_ref)
    if pending_secret_ref == state.secret_ref:
        raise CredentialCannotRotateError(state.id, state.status, "start_rotation_same_ref")

    pending_public_material_ref = (
        command.new_public_material_ref.strip()
        if command.new_public_material_ref is not None
        else None
    )
    if pending_public_material_ref == "":
        pending_public_material_ref = None

    return [
        CredentialRotationStarted(
            credential_id=state.id,
            pending_secret_ref=pending_secret_ref,
            pending_public_material_ref=pending_public_material_ref,
            rotation_started_by=rotation_started_by,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
