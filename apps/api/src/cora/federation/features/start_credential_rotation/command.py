"""The `StartCredentialRotation` command: intent dataclass for this slice.

`credential_id` is the target Credential aggregate.
`new_secret_ref` and `new_public_material_ref` are opaque pointers to
material that has already been provisioned in the SecretStore adapter
(per AH#6 of [[project_federation_port_design]] Memo 1, raw secret
bytes never cross this boundary). The invoking principal's id is
supplied separately by the application handler at call time and
stamped onto the emitted event as `rotation_started_by_actor_id`.

Strict-not-idempotent transition: starting a rotation against an
already Rotating or Revoked credential raises
`CredentialCannotRotateError` (HTTP 409). Starting a rotation with a
`new_secret_ref` equal to the credential's current `secret_ref` is
rejected with the same error (`attempted="start_rotation_same_ref"`)
to surface caller mistakes loudly rather than silently writing a
no-op rotation event.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StartCredentialRotation:
    """Operator starts a rotation against an Active credential (Active -> Rotating).

    Single-source: requires the Credential to be in `Active` status.
    The pending refs sit alongside the current refs until either
    `complete_credential_rotation` promotes them or
    `abort_credential_rotation` discards them.
    """

    credential_id: UUID
    new_secret_ref: str
    new_public_material_ref: str | None
