"""Vertical slice for the `RegisterCredential` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.federation.features import register_credential

    cmd = register_credential.RegisterCredential(
        facility_code="aps-2bm",
        audience="peer.example.org",
        purpose=CredentialPurpose.SIGNING,
        secret_ref="vault://kv/cora/federation/aps-2bm/signing#v1",
        public_material_ref=None,
        expires_at=None,
    )
    handler = register_credential.bind(deps)
    credential_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.federation.features.register_credential import tool
from cora.federation.features.register_credential.command import RegisterCredential
from cora.federation.features.register_credential.decider import decide
from cora.federation.features.register_credential.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.federation.features.register_credential.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterCredential",
    "bind",
    "decide",
    "router",
    "tool",
]
