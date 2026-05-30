"""The `CompleteCredentialRotation` command: intent dataclass for this slice.

`credential_id` is the target Credential aggregate. The invoking
principal's id is supplied separately by the application handler at
call time (envelope `principal_id` denorms to
`rotation_completed_by_actor_id` on the emitted event).

Strict-not-idempotent transition: completing a rotation on a credential
that is not in `Rotating` status raises `CredentialCannotRotateError`
-> HTTP 409. HTTP-layer idempotency adds no value for transitions; the
strict guard at the decider is the contract.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CompleteCredentialRotation:
    """Operator completes an in-flight rotation (Rotating -> Active).

    Single-source: requires the Credential to be in `Rotating` status
    with pending refs populated. The evolver promotes the pending refs
    to current on apply.
    """

    credential_id: UUID
