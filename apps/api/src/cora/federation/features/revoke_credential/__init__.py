"""Vertical slice for the `RevokeCredential` command.

Module-as-namespace surface, symmetric with the other Federation
Credential lifecycle slices:

    from cora.federation.features import revoke_credential

    cmd = revoke_credential.RevokeCredential(
        credential_id=..., reason=None
    )
    handler = revoke_credential.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Terminal: once revoked, a credential cannot be revived. Mirrors the
`revoke_permit` and `deregister_supply` lifecycle-terminal precedent.
Strict-not-idempotent: revoking an already-Revoked credential raises
`CredentialCannotRevokeError` (HTTP 409) rather than silently
succeeding, so callers always see the transition gesture they
performed.

Cross-BC: this slice writes `CredentialRevoked` on the Federation
Credential stream AND a `DecisionRegistered` audit on the Decision
stream in one transaction. Revoking a credential is a security-
touching action (compromised secret retirement, peer material pull),
so the audit emission is atomic with the revocation; mirrors the
`register_credential` cross-BC genesis pattern.
"""

from cora.federation.features.revoke_credential import tool
from cora.federation.features.revoke_credential.command import RevokeCredential
from cora.federation.features.revoke_credential.decider import decide
from cora.federation.features.revoke_credential.handler import Handler, bind
from cora.federation.features.revoke_credential.route import router

__all__ = [
    "Handler",
    "RevokeCredential",
    "bind",
    "decide",
    "router",
    "tool",
]
