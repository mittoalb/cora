"""Vertical slice for the `AbortCredentialRotation` command.

Module-as-namespace surface, symmetric with the other Federation
transition slices:

    from cora.federation.features import abort_credential_rotation

    cmd = abort_credential_rotation.AbortCredentialRotation(
        credential_id=...,
        aborted_by_actor_id=...,
        reason=None,
    )
    handler = abort_credential_rotation.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Single-source transition: requires the Credential to be in `Rotating`
status. Strict-not-idempotent: aborting a rotation against a
non-Rotating credential raises `CredentialCannotRotateError` (HTTP
409). The evolver clears the pending refs on apply; the current
`secret_ref` / `public_material_ref` are unchanged.
"""

from cora.federation.features.abort_credential_rotation import tool
from cora.federation.features.abort_credential_rotation.command import (
    AbortCredentialRotation,
)
from cora.federation.features.abort_credential_rotation.decider import decide
from cora.federation.features.abort_credential_rotation.handler import Handler, bind
from cora.federation.features.abort_credential_rotation.route import router

__all__ = [
    "AbortCredentialRotation",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
