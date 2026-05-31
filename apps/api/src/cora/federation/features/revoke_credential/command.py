"""The `RevokeCredential` command: intent dataclass for this slice.

`credential_id` is the target Credential aggregate. `reason` is
operator-supplied free text captured at the API boundary for
audit-log breadcrumb purposes (for example, "credential compromise",
"audience deprecation", "peer rotation policy"). `reason` flows
through to the emitted `CredentialRevoked` event payload so
operator context survives on the immutable event log.

The principal-id of the invoker is supplied separately by the
application handler at call time and stamped onto the
`CredentialRevoked` event as `revoked_by_actor_id`.

Revoking is terminal: any non-Revoked status (Active, Rotating)
transitions to Revoked. Strict-not-idempotent at the decider:
re-revoking an already-Revoked credential raises
`CredentialCannotRevokeError` (HTTP 409) per the same convention as
`revoke_permit` / `deregister_supply` / `mark_supply_available`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RevokeCredential:
    """Operator revokes a Credential (terminal: any non-Revoked -> Revoked).

    Widest-source transition: any of Active or Rotating transitions to
    Revoked. Strict-not-idempotent: revoking an already-Revoked
    credential raises `CredentialCannotRevokeError`.
    """

    credential_id: UUID
    reason: str | None = None
