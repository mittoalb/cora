"""Compose the Federation BC's handlers from `Kernel`.

`wire_federation(deps)` is invoked once from the FastAPI lifespan
and the returned `FederationHandlers` bundle is stored on
`app.state.federation`. Routes and MCP tools pull their handler out
of that bundle. New slices add a new field on `FederationHandlers`
and a single line in this factory.

Cross-cutting decorators applied here:

  1. `bind(deps)`: bare handler.
  2. `with_idempotency` (create-style commands only): Idempotency-Key
     support. Wrapped before tracing so cache-hits and cache-misses
     both attribute to the tracing span.
  3. `with_tracing`: OTel span around every handler call.

Stage 2b lands the five Permit lifecycle slices: `register_permit`
(create-style; idempotency-wrapped) plus the four transitions
(`activate_permit`, `suspend_permit`, `resume_permit`,
`revoke_permit`). Stage 2c-credential lands the five Credential
lifecycle slices: `register_credential` (create-style;
idempotency-wrapped) plus the four transitions
(`start_credential_rotation`, `complete_credential_rotation`,
`abort_credential_rotation`, `revoke_credential`). Seal slices land
in Stage 2c-seal.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.federation.features import (
    abort_credential_rotation,
    activate_permit,
    complete_credential_rotation,
    register_credential,
    register_permit,
    resume_permit,
    revoke_credential,
    revoke_permit,
    start_credential_rotation,
    suspend_permit,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "federation"


@dataclass(frozen=True)
class FederationHandlers:
    """The Federation BC's handler bundle, each closed over Kernel.

    Stage 2b: five Permit lifecycle slices (register + four
    transitions). Stage 2c-credential: five Credential lifecycle
    slices (register + four transitions). Seal slices land in
    Stage 2c-seal.
    """

    register_permit: register_permit.IdempotentHandler
    activate_permit: activate_permit.Handler
    suspend_permit: suspend_permit.Handler
    resume_permit: resume_permit.Handler
    revoke_permit: revoke_permit.Handler
    register_credential: register_credential.IdempotentHandler
    start_credential_rotation: start_credential_rotation.Handler
    complete_credential_rotation: complete_credential_rotation.Handler
    abort_credential_rotation: abort_credential_rotation.Handler
    revoke_credential: revoke_credential.Handler


def wire_federation(deps: Kernel) -> FederationHandlers:
    """Build the Federation BC handlers from shared dependencies."""
    return FederationHandlers(
        register_permit=with_tracing(
            with_idempotency(
                register_permit.bind(deps),
                deps.idempotency_store,
                command_name="RegisterPermit",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterPermit",
            bc=_BC,
        ),
        activate_permit=with_tracing(
            activate_permit.bind(deps),
            command_name="ActivatePermit",
            bc=_BC,
        ),
        suspend_permit=with_tracing(
            suspend_permit.bind(deps),
            command_name="SuspendPermit",
            bc=_BC,
        ),
        resume_permit=with_tracing(
            resume_permit.bind(deps),
            command_name="ResumePermit",
            bc=_BC,
        ),
        revoke_permit=with_tracing(
            revoke_permit.bind(deps),
            command_name="RevokePermit",
            bc=_BC,
        ),
        register_credential=with_tracing(
            with_idempotency(
                register_credential.bind(deps),
                deps.idempotency_store,
                command_name="RegisterCredential",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterCredential",
            bc=_BC,
        ),
        start_credential_rotation=with_tracing(
            start_credential_rotation.bind(deps),
            command_name="StartCredentialRotation",
            bc=_BC,
        ),
        complete_credential_rotation=with_tracing(
            complete_credential_rotation.bind(deps),
            command_name="CompleteCredentialRotation",
            bc=_BC,
        ),
        abort_credential_rotation=with_tracing(
            abort_credential_rotation.bind(deps),
            command_name="AbortCredentialRotation",
            bc=_BC,
        ),
        revoke_credential=with_tracing(
            revoke_credential.bind(deps),
            command_name="RevokeCredential",
            bc=_BC,
        ),
    )


__all__ = ["FederationHandlers", "wire_federation"]
