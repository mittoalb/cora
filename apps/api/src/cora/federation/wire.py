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
  3. `with_tracing`: OTel span around every handler call. Query
     handlers pass `kind="query"` so the span is tagged accordingly.

The bundle wires five Permit lifecycle slices: `define_permit`
(create-style; idempotency-wrapped) plus the four transitions
(`activate_permit`, `suspend_permit`, `resume_permit`,
`revoke_permit`); five Credential lifecycle slices:
`register_credential` (create-style; idempotency-wrapped) plus the
four transitions (`start_credential_rotation`,
`complete_credential_rotation`, `abort_credential_rotation`,
`revoke_credential`); five Seal lifecycle slices: `initialize_seal`
(genesis; idempotency-wrapped; cross-BC) plus the four transitions
(`sign_seal_pointer`, `rotate_seal_online_key`,
`start_seal_republishing`, `complete_seal_republishing`); and six
read-side slices: three list queries (`list_permits`,
`list_credentials`, `list_seals`) backed by the shared `list_query`
factory, and three by-id queries (`get_permit`, `get_credential`,
`get_seal`) that compose `load_X` (event-store fold) with
`load_X_timestamps` (projection fold) into a `XView` bundle.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.federation.features import (
    abort_credential_rotation,
    activate_permit,
    complete_credential_rotation,
    complete_seal_republishing,
    decommission_facility,
    define_permit,
    get_credential,
    get_permit,
    get_seal,
    initialize_seal,
    list_credentials,
    list_permits,
    list_seals,
    register_credential,
    register_facility,
    resume_permit,
    revoke_credential,
    revoke_permit,
    rotate_seal_online_key,
    sign_seal_pointer,
    start_credential_rotation,
    start_seal_republishing,
    suspend_permit,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "federation"


@dataclass(frozen=True)
class FederationHandlers:
    """The Federation BC's handler bundle, each closed over Kernel.

    Five Permit lifecycle slices (define + four transitions), five
    Credential lifecycle slices (register + four transitions), five
    Seal lifecycle slices (initialize + four transitions), and six
    read-side slices (three list + three get-by-id).
    """

    define_permit: define_permit.IdempotentHandler
    activate_permit: activate_permit.Handler
    suspend_permit: suspend_permit.Handler
    resume_permit: resume_permit.Handler
    revoke_permit: revoke_permit.Handler
    register_credential: register_credential.IdempotentHandler
    start_credential_rotation: start_credential_rotation.Handler
    complete_credential_rotation: complete_credential_rotation.Handler
    abort_credential_rotation: abort_credential_rotation.Handler
    revoke_credential: revoke_credential.Handler
    initialize_seal: initialize_seal.IdempotentHandler
    sign_seal_pointer: sign_seal_pointer.Handler
    rotate_seal_online_key: rotate_seal_online_key.Handler
    start_seal_republishing: start_seal_republishing.Handler
    complete_seal_republishing: complete_seal_republishing.Handler
    register_facility: register_facility.IdempotentHandler
    decommission_facility: decommission_facility.Handler
    list_permits: list_permits.Handler
    get_permit: get_permit.Handler
    list_credentials: list_credentials.Handler
    get_credential: get_credential.Handler
    list_seals: list_seals.Handler
    get_seal: get_seal.Handler


def wire_federation(deps: Kernel) -> FederationHandlers:
    """Build the Federation BC handlers from shared dependencies."""
    return FederationHandlers(
        define_permit=with_tracing(
            with_idempotency(
                define_permit.bind(deps),
                deps.idempotency_store,
                command_name="DefinePermit",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefinePermit",
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
        initialize_seal=with_tracing(
            with_idempotency(
                initialize_seal.bind(deps),
                deps.idempotency_store,
                command_name="InitializeSeal",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="InitializeSeal",
            bc=_BC,
        ),
        sign_seal_pointer=with_tracing(
            sign_seal_pointer.bind(deps),
            command_name="SignSealPointer",
            bc=_BC,
        ),
        rotate_seal_online_key=with_tracing(
            rotate_seal_online_key.bind(deps),
            command_name="RotateSealOnlineKey",
            bc=_BC,
        ),
        start_seal_republishing=with_tracing(
            start_seal_republishing.bind(deps),
            command_name="StartSealRepublishing",
            bc=_BC,
        ),
        complete_seal_republishing=with_tracing(
            complete_seal_republishing.bind(deps),
            command_name="CompleteSealRepublishing",
            bc=_BC,
        ),
        register_facility=with_tracing(
            with_idempotency(
                register_facility.bind(deps),
                deps.idempotency_store,
                command_name="RegisterFacility",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterFacility",
            bc=_BC,
        ),
        decommission_facility=with_tracing(
            decommission_facility.bind(deps),
            command_name="DecommissionFacility",
            bc=_BC,
        ),
        list_permits=with_tracing(
            list_permits.bind(deps),
            command_name="ListPermits",
            bc=_BC,
            kind="query",
        ),
        get_permit=with_tracing(
            get_permit.bind(deps),
            command_name="GetPermit",
            bc=_BC,
            kind="query",
        ),
        list_credentials=with_tracing(
            list_credentials.bind(deps),
            command_name="ListCredentials",
            bc=_BC,
            kind="query",
        ),
        get_credential=with_tracing(
            get_credential.bind(deps),
            command_name="GetCredential",
            bc=_BC,
            kind="query",
        ),
        list_seals=with_tracing(
            list_seals.bind(deps),
            command_name="ListSeals",
            bc=_BC,
            kind="query",
        ),
        get_seal=with_tracing(
            get_seal.bind(deps),
            command_name="GetSeal",
            bc=_BC,
            kind="query",
        ),
    )


__all__ = ["FederationHandlers", "wire_federation"]
