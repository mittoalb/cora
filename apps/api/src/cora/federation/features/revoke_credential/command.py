"""The `RevokeCredential` command: intent dataclass for this slice.

`credential_id` is the target Credential aggregate. The principal-id
of the invoker is supplied separately by the application handler at
call time and stamped onto the `CredentialRevoked` event as
`revoked_by_actor_id`; revoke is operator-driven (or compromise-
driven) and carries no additional payload beyond an optional reason.

The optional `reason` is accepted at the schema boundary so callers
can surface human-readable intent in the audit trail, but it is NOT
persisted on the `CredentialRevoked` event today. The
`DecisionRegistered` audit emitted alongside the revoke carries the
operator-supplied `reason` in its `reasoning` field if a future
extension wires it through; until then the field is accepted-and-
ignored so the command shape stays forward-compatible.

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
