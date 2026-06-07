"""The `AbortCredentialRotation` command: intent dataclass for this slice.

`credential_id` is the target Credential aggregate. `reason` is
operator-supplied free text captured at the API boundary for
audit-log breadcrumb purposes (for example, "peer refused new
material", "SecretStore generation failed", "operator changed
their mind"). `reason` flows through to the emitted
`CredentialRotationAborted` event payload so operator context
survives on the immutable event log.

The invoking principal's id is supplied separately by the
application handler at call time (envelope `principal_id` denorms
to `rotation_aborted_by` on the emitted event).

Strict-not-idempotent transition: aborting a rotation on a
credential that is not in `Rotating` status raises
`CredentialCannotRotateError` -> HTTP 409. HTTP-layer idempotency
adds no value for transitions; the strict guard at the decider
is the contract.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AbortCredentialRotation:
    """Operator aborts an in-flight rotation (Rotating -> Active).

    Single-source: requires the Credential to be in `Rotating`
    status. The evolver clears the pending refs on apply; the
    current `secret_ref` / `public_material_ref` are unchanged.
    """

    credential_id: UUID
    aborted_by: UUID
    reason: str | None = None
