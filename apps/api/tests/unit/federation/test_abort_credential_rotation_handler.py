"""Application-handler tests for the `abort_credential_rotation` slice.

Covers the authz denial path (no event written), strict-not-idempotent
posture on re-abort (Active source-state rejection after a successful
abort), FSM precondition rejection on Active / Revoked, not-found on
an unknown credential, and the success path's event envelope shape
(correlation_id, causation_id, and the `rotation_aborted_by_actor_id`
denorm on payload).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.credential import (
    CredentialCannotRotateError,
    CredentialNotFoundError,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import abort_credential_rotation
from cora.federation.features.abort_credential_rotation import (
    AbortCredentialRotation,
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
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_OTHER_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000088")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEXT_EVENT_ID],
        now=_T2,
        event_store=event_store,
        deny=deny,
    )


def _command(reason: str | None = "peer refused new material") -> AbortCredentialRotation:
    return AbortCredentialRotation(
        credential_id=_CREDENTIAL_ID,
        aborted_by_actor_id=_PRINCIPAL_ID,
        reason=reason,
    )


@pytest.mark.unit
async def test_abort_credential_rotation_handler_appends_event_to_rotating_credential() -> None:
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
    handler = abort_credential_rotation.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Credential", _CREDENTIAL_ID)
    assert version == 3
    stored = events[-1]
    assert stored.event_type == "CredentialRotationAborted"
    assert stored.payload["rotation_aborted_by_actor_id"] == str(_PRINCIPAL_ID)
    assert stored.payload["credential_id"] == str(_CREDENTIAL_ID)
    assert stored.payload["reason"] == "peer refused new material"
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None


@pytest.mark.unit
async def test_abort_credential_rotation_handler_event_payload_carries_reason() -> None:
    """`reason` flows from the command through the decider onto the
    emitted `CredentialRotationAborted` event payload (audit context
    survives on the immutable event log)."""
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
    handler = abort_credential_rotation.bind(deps)
    await handler(
        _command(reason="SecretStore generation failed"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Credential", _CREDENTIAL_ID)
    assert events[-1].payload["reason"] == "SecretStore generation failed"


@pytest.mark.unit
async def test_abort_credential_rotation_handler_event_payload_records_none_reason() -> None:
    """When the operator omits `reason`, the emitted event carries
    None on the payload (round-trip stays clean)."""
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
    handler = abort_credential_rotation.bind(deps)
    await handler(
        _command(reason=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Credential", _CREDENTIAL_ID)
    assert events[-1].payload["reason"] is None


@pytest.mark.unit
async def test_abort_credential_rotation_handler_raises_not_found_for_unknown_credential() -> None:
    deps = _build_deps()
    handler = abort_credential_rotation.bind(deps)
    with pytest.raises(CredentialNotFoundError):
        await handler(
            _command(reason=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_abort_credential_rotation_handler_raises_cannot_rotate_when_active() -> None:
    """An Active credential has no rotation in flight; abort rejects."""
    store = InMemoryEventStore()
    await seed_active_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        registered_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = abort_credential_rotation.bind(deps)
    with pytest.raises(CredentialCannotRotateError):
        await handler(
            _command(reason=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_abort_credential_rotation_handler_raises_cannot_rotate_when_revoked() -> None:
    """Revoked is terminal; abort rejects."""
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
    handler = abort_credential_rotation.bind(deps)
    with pytest.raises(CredentialCannotRotateError):
        await handler(
            _command(reason=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_abort_credential_rotation_handler_strict_not_idempotent_on_re_abort() -> None:
    """After a successful abort the credential is Active; re-aborting MUST
    raise rather than no-op."""
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
    handler = abort_credential_rotation.bind(deps)
    await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _, version_after_abort = await store.load("Credential", _CREDENTIAL_ID)
    assert version_after_abort == 3
    with pytest.raises(CredentialCannotRotateError):
        await handler(
            _command(reason="re-abort"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version_after_reject = await store.load("Credential", _CREDENTIAL_ID)
    assert version_after_reject == 3  # untouched after re-abort rejection


@pytest.mark.unit
async def test_abort_credential_rotation_handler_denies_via_authorize_port() -> None:
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
    deps = _build_deps(event_store=store, deny=True)
    handler = abort_credential_rotation.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(reason=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_abort_credential_rotation_handler_denied_does_not_write_to_stream() -> None:
    """Authz-denial MUST NOT leave events on the stream."""
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
    deps = _build_deps(event_store=store, deny=True)
    handler = abort_credential_rotation.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            _command(reason=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version = await store.load("Credential", _CREDENTIAL_ID)
    assert version == 2  # untouched after Registered + RotationStarted seed


@pytest.mark.unit
async def test_abort_credential_rotation_handler_records_principal_as_aborted_by_actor_id() -> None:
    """The handler injects the request envelope's `principal_id` as
    `rotation_aborted_by_actor_id` on the emitted event (audit anchor
    for the operator gesture), regardless of who started the
    rotation."""
    store = InMemoryEventStore()
    # Seed Registered + RotationStarted BY a different actor; the aborter
    # should still be recorded as the invoking principal.
    await seed_rotating_credential(
        store,
        credential_id=_CREDENTIAL_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        rotation_started_event_id=_ROTATION_STARTED_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_OTHER_PRINCIPAL_ID,
        registered_at=_T0,
        rotation_started_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = abort_credential_rotation.bind(deps)
    await handler(
        _command(reason=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, _ = await store.load("Credential", _CREDENTIAL_ID)
    assert events[-1].payload["rotation_aborted_by_actor_id"] == str(_PRINCIPAL_ID)
