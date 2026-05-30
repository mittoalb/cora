"""Vertical slice for the `RevokePermit` command.

Module-as-namespace surface, symmetric with the other Federation
transition slices:

    from cora.federation.features import revoke_permit

    cmd = revoke_permit.RevokePermit(permit_id=..., reason=None)
    handler = revoke_permit.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Terminal: once revoked, a permit cannot be revived. Mirrors the
deregister_supply lifecycle-terminal precedent. Strict-not-idempotent:
revoking an already-Revoked permit raises `PermitCannotRevokeError`
(HTTP 409) rather than silently succeeding, so callers always see the
transition gesture they performed.
"""

from cora.federation.features.revoke_permit import tool
from cora.federation.features.revoke_permit.command import RevokePermit
from cora.federation.features.revoke_permit.decider import decide
from cora.federation.features.revoke_permit.handler import Handler, bind
from cora.federation.features.revoke_permit.route import router

__all__ = [
    "Handler",
    "RevokePermit",
    "bind",
    "decide",
    "router",
    "tool",
]
