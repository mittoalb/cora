"""Vertical slice for the `StartCredentialRotation` command.

Module-as-namespace surface, symmetric with the other Federation
transition slices:

    from cora.federation.features import start_credential_rotation

    cmd = start_credential_rotation.StartCredentialRotation(
        credential_id=...,
        new_secret_ref=...,
        new_public_material_ref=...,
    )
    handler = start_credential_rotation.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Single-source transition: requires the Credential to be in `Active`
status. Strict-not-idempotent: starting a rotation against an already
Rotating or Revoked credential raises `CredentialCannotRotateError`
(HTTP 409). The aggregate captures the operator-supplied pending
refs; the evolver promotes them on `complete_credential_rotation` or
discards them on `abort_credential_rotation`.
"""

from cora.federation.features.start_credential_rotation import tool
from cora.federation.features.start_credential_rotation.command import (
    StartCredentialRotation,
)
from cora.federation.features.start_credential_rotation.decider import decide
from cora.federation.features.start_credential_rotation.handler import Handler, bind
from cora.federation.features.start_credential_rotation.route import router

__all__ = [
    "Handler",
    "StartCredentialRotation",
    "bind",
    "decide",
    "router",
    "tool",
]
