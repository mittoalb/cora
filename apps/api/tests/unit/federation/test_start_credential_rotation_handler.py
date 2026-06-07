"""Application-handler tests for the `start_credential_rotation` slice.

Covers the authz denial path (no event written), the FSM precondition
rejection on non-Active source-states (Rotating / Revoked), not-found
on an unknown credential, ref-shape validation propagation from the
decider, strict-not-idempotent posture on replay against a now-
Rotating credential, and the success path's event envelope shape
(correlation_id, causation_id, and the `rotation_started_by`
denorm on payload).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.credential import (
    CredentialCannotRotateError,
    CredentialNotFoundError,
    InvalidCredentialSecretRefError,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import start_credential_rotation
from cora.federation.features.start_credential_rotation import (
    StartCredentialRotation,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.federation._helpers import (
    seed_active_credential,
    seed_revoked_credential,
    seed_rotating_credential,
)

_T0 = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed002")
_ROTATION_STARTED_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed003")
_REVOKE_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed004")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed005")
_FOLLOWUP_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed006")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_OTHER_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000088")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CURRENT_SECRET_REF = "vault://current/v1"
_PENDING_SECRET_REF = "vault://pending/v2"
_PENDING_PUBLIC_REF = "vault://pending/pub/v2"


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    ids: list[UUID] | None = None,
) -> Kernel:
    return _build_deps_shared(
        ids=ids if ids is not None else [_NEXT_EVENT_ID],
        now=_T2,
        event_store=event_store,
        deny=deny,
    )


def _command(
    *,
    new_secret_ref: str = _PENDING_SECRET_REF,
    new_public_material_ref: str | None = _PENDING_PUBLIC_REF,
) -> StartCredentialRotation:
    return StartCredentialRotation(
        credential_id=_CREDENTIAL_ID,
        new_secret_ref=new_secret_ref,
        new_public_material_ref=new_public_material_ref,
    )


@pytest.mark.unit
async def test_start_credential_rotation_handler_appends_event_to_active_credential() -> None:
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
        secret_ref=_CURRENT_SECRET_REF,
    )
    deps = _build_deps(event_store=store)
    handler = start_credential_rotation.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Credential", _CREDENTIAL_ID)
    assert version == 2
    stored = events[-1]
    assert stored.event_type == "CredentialRotationStarted"
    assert stored.payload["credential_id"] == str(_CREDENTIAL_ID)
    assert stored.payload["pending_secret_ref"] == _PENDING_SECRET_REF
    assert stored.payload["pending_public_material_ref"] == _PENDING_PUBLIC_REF
    assert stored.payload["rotation_started_by"] == str(_PRINCIPAL_ID)
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None


@pytest.mark.unit
async def test_start_credential_rotation_handler_propagates_causation_id() -> None:
    """Optional `causation_id` on the request envelope rides through to the event."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
        secret_ref=_CURRENT_SECRET_REF,
    )
    causation = UUID("01900000-0000-7000-8000-0000000000cc")
    deps = _build_deps(event_store=store)
    handler = start_credential_rotation.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )
    events, _ = await store.load("Credential", _CREDENTIAL_ID)
    assert events[-1].causation_id == causation


@pytest.mark.unit
async def test_start_credential_rotation_handler_raises_not_found_for_unknown_credential() -> None:
    deps = _build_deps()
    handler = start_credential_rotation.bind(deps)
    with pytest.raises(CredentialNotFoundError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_start_credential_rotation_handler_raises_cannot_rotate_when_rotating() -> None:
    """A Rotating credential already has a rotation in flight; start rejects."""
    store = InMemoryEventStore()
    await seed_rotating_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        rotation_started_event_id=_ROTATION_STARTED_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        rotation_started_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = start_credential_rotation.bind(deps)
    with pytest.raises(CredentialCannotRotateError):
        await handler(
            _command(new_secret_ref="vault://pending/v3"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_start_credential_rotation_handler_raises_cannot_rotate_when_revoked() -> None:
    """Revoked is terminal; start_rotation rejects."""
    store = InMemoryEventStore()
    await seed_revoked_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        revoke_event_id=_REVOKE_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        revoked_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = start_credential_rotation.bind(deps)
    with pytest.raises(CredentialCannotRotateError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_start_credential_rotation_handler_raises_on_empty_new_secret_ref() -> None:
    """Decider-layer ref-shape validation surfaces through the handler."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
        secret_ref=_CURRENT_SECRET_REF,
    )
    deps = _build_deps(event_store=store)
    handler = start_credential_rotation.bind(deps)
    with pytest.raises(InvalidCredentialSecretRefError):
        await handler(
            _command(new_secret_ref="   "),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_start_credential_rotation_handler_raises_on_same_ref_as_current() -> None:
    """Supplying a `new_secret_ref` equal to the current `secret_ref` rejects."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
        secret_ref=_CURRENT_SECRET_REF,
    )
    deps = _build_deps(event_store=store)
    handler = start_credential_rotation.bind(deps)
    with pytest.raises(CredentialCannotRotateError) as exc:
        await handler(
            _command(new_secret_ref=_CURRENT_SECRET_REF),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.attempted == "start_rotation_same_ref"


@pytest.mark.unit
async def test_start_credential_rotation_handler_replay_raises_cannot_rotate_error() -> None:
    """After a successful start the credential is Rotating; replaying MUST raise."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
        secret_ref=_CURRENT_SECRET_REF,
    )
    deps = _build_deps(event_store=store, ids=[_NEXT_EVENT_ID, _FOLLOWUP_EVENT_ID])
    handler = start_credential_rotation.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version_after_start = await store.load("Credential", _CREDENTIAL_ID)
    assert version_after_start == 2
    with pytest.raises(CredentialCannotRotateError):
        await handler(
            _command(new_secret_ref="vault://pending/v3"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version_after_reject = await store.load("Credential", _CREDENTIAL_ID)
    assert version_after_reject == 2  # untouched after replay rejection


@pytest.mark.unit
async def test_start_credential_rotation_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
        secret_ref=_CURRENT_SECRET_REF,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = start_credential_rotation.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_start_credential_rotation_handler_denied_does_not_write_to_stream() -> None:
    """Authz-denial MUST NOT leave events on the stream."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
        secret_ref=_CURRENT_SECRET_REF,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = start_credential_rotation.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Credential", _CREDENTIAL_ID)
    assert version == 1  # untouched after CredentialRegistered seed


@pytest.mark.unit
async def test_start_credential_rotation_handler_records_rotation_started_by() -> None:
    """The handler injects the request envelope's `principal_id` as
    `rotation_started_by` on the emitted event, regardless of
    who registered the credential."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_OTHER_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
        secret_ref=_CURRENT_SECRET_REF,
    )
    deps = _build_deps(event_store=store)
    handler = start_credential_rotation.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Credential", _CREDENTIAL_ID)
    assert events[-1].payload["rotation_started_by"] == str(_PRINCIPAL_ID)


@pytest.mark.unit
async def test_start_credential_rotation_handler_accepts_none_public_material_ref() -> None:
    """A symmetric-purpose credential can rotate without a public counterpart."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
        secret_ref=_CURRENT_SECRET_REF,
    )
    deps = _build_deps(event_store=store)
    handler = start_credential_rotation.bind(deps)
    await handler(
        _command(new_public_material_ref=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Credential", _CREDENTIAL_ID)
    assert events[-1].payload["pending_public_material_ref"] is None
