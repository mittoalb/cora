"""Pure decider for the `RevokeCredential` command.

Widest-source terminal transition: any non-Revoked status (Active or
Rotating) transitions to Revoked. Strict-not-idempotent: re-revoking
an already-Revoked credential raises `CredentialCannotRevokeError`
(HTTP 409) per the same convention as `revoke_permit` /
`deregister_supply` / `mark_supply_available`.

Revocation is intentionally accepted PAST `expires_at` so an expired
credential can be terminally retired without first being restored;
this matches the locked aggregate-state docstring on
`CredentialExpiredError`.

`revoked_by_actor_id` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the
emitted `CredentialRevoked` event for the audit denorm.

## Validation

  - State must not be None (credential must exist)
    -> CredentialNotFoundError
  - Current status must not be Revoked
    -> CredentialCannotRevokeError
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.credential import (
    Credential,
    CredentialCannotRevokeError,
    CredentialNotFoundError,
    CredentialRevoked,
    CredentialStatus,
)
from cora.federation.features.revoke_credential.command import RevokeCredential


def decide(
    state: Credential | None,
    command: RevokeCredential,
    *,
    now: datetime,
    revoked_by_actor_id: UUID,
) -> list[CredentialRevoked]:
    """Decide the events produced by revoking a Credential.

    Invariants:
      - State must not be None -> CredentialNotFoundError
      - Current status must not be Revoked
        -> CredentialCannotRevokeError
    """
    if state is None:
        raise CredentialNotFoundError(command.credential_id)
    if state.status is CredentialStatus.REVOKED:
        raise CredentialCannotRevokeError(state.id)

    return [
        CredentialRevoked(
            credential_id=state.id,
            revoked_by_actor_id=revoked_by_actor_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
