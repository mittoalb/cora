"""Vertical slice for the `CompleteCredentialRotation` command.

Module-as-namespace surface, symmetric with the other Federation
transition slices:

    from cora.federation.features import complete_credential_rotation

    cmd = complete_credential_rotation.CompleteCredentialRotation(
        credential_id=...,
    )
    handler = complete_credential_rotation.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Single-source transition (Rotating -> Active): the evolver promotes the
pending refs captured by `CredentialRotationStarted` to the current
refs. Strict-not-idempotent at the decider: completing on a non-
Rotating credential raises `CredentialCannotRotateError` (HTTP 409).
"""

from cora.federation.features.complete_credential_rotation import tool
from cora.federation.features.complete_credential_rotation.command import (
    CompleteCredentialRotation,
)
from cora.federation.features.complete_credential_rotation.decider import decide
from cora.federation.features.complete_credential_rotation.handler import Handler, bind
from cora.federation.features.complete_credential_rotation.route import router

__all__ = [
    "CompleteCredentialRotation",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
