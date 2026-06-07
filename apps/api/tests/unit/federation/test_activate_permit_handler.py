"""Application-handler tests for the `activate_permit` slice.

Covers authz denial (with stream-untouched assertion), envelope
propagation (correlation_id), the `PermitNotFoundError` and
`PermitCannotActivateError` propagation paths, and strict-not-idempotent
re-activation (replaying activate against an Active stream raises).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.permit import (
    PermitCannotActivateError,
    PermitNotFoundError,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features import activate_permit
from cora.federation.features.activate_permit import ActivatePermit
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.federation._helpers import (
    seed_active_permit,
    seed_defined_permit,
    seed_suspended_permit,
)

_T0 = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_T3 = datetime(2026, 5, 30, 13, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed002")
_ACTIVATE_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed003")
_SUSPEND_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed004")
_NEXT_EVENT_ID = UUID("01900000-0000-7000-8000-000000fed005")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEXT_EVENT_ID],
        now=_T3,
        event_store=event_store,
        deny=deny,
    )


@pytest.mark.unit
async def test_activate_permit_handler_appends_event_for_defined_permit() -> None:
    store = InMemoryEventStore()
    await seed_defined_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = activate_permit.bind(deps)
    await handler(
        ActivatePermit(permit_id=_PERMIT_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    events, version = await store.load("Permit", _PERMIT_ID)
    assert version == 2
    assert events[-1].event_type == "PermitActivated"
    assert events[-1].payload["permit_id"] == str(_PERMIT_ID)
    assert events[-1].payload["activated_by"] == str(_PRINCIPAL_ID)
    assert events[-1].correlation_id == _CORRELATION_ID
    assert events[-1].causation_id is None


@pytest.mark.unit
async def test_activate_permit_handler_raises_not_found_for_unknown_permit() -> None:
    deps = _build_deps()
    handler = activate_permit.bind(deps)
    with pytest.raises(PermitNotFoundError):
        await handler(
            ActivatePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_activate_permit_handler_raises_on_already_active_permit() -> None:
    """Re-activating an already-Active permit raises (no replay caching)."""
    store = InMemoryEventStore()
    await seed_active_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        activate_event_id=_ACTIVATE_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = activate_permit.bind(deps)
    with pytest.raises(PermitCannotActivateError):
        await handler(
            ActivatePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version_after = await store.load("Permit", _PERMIT_ID)
    assert version_after == 2


@pytest.mark.unit
async def test_activate_permit_handler_raises_cannot_activate_when_suspended() -> None:
    store = InMemoryEventStore()
    await seed_suspended_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        activate_event_id=_ACTIVATE_EVENT_ID,
        suspend_event_id=_SUSPEND_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        activated_at=_T1,
        suspended_at=_T2,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store)
    handler = activate_permit.bind(deps)
    with pytest.raises(PermitCannotActivateError):
        await handler(
            ActivatePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_activate_permit_handler_denies_via_authorize_port() -> None:
    store = InMemoryEventStore()
    await seed_defined_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = activate_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ActivatePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_activate_permit_handler_denied_does_not_write_to_stream() -> None:
    """Authz denial MUST NOT leave any new events on the stream."""
    store = InMemoryEventStore()
    await seed_defined_permit(
        store,
        permit_id=_PERMIT_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        defined_at=_T0,
        expires_at=_EXPIRES_AT,
    )
    deps = _build_deps(event_store=store, deny=True)
    handler = activate_permit.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ActivatePermit(permit_id=_PERMIT_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    _, version_after = await store.load("Permit", _PERMIT_ID)
    assert version_after == 1  # PermitDefined only
